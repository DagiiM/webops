"""Exclusive, supervised queue worker. Never replays potentially non-idempotent work."""
import fcntl
import json
import logging
import signal
import threading
import time
from django.db import close_old_connections
from .factory import get_background_processor

logger=logging.getLogger(__name__)
DEPLOY_TASKS={"apps.deployments.tasks.application.deploy_application","apps.deployments.tasks.llm.deploy_llm_model"}

def record_failure(job,message):
    # Only change an unfinished build. A running process may have completed before
    # the worker died; preserve its state for operator reconciliation.
    from apps.deployments.models import BaseDeployment,DeploymentLog
    ident=json.loads(job["payload"])["args"][0]
    d=BaseDeployment.objects.filter(pk=ident,is_deleted=False).first()
    if d:
        if job["task"] in DEPLOY_TASKS:
            BaseDeployment.objects.filter(pk=ident,status__in=["pending","building"],is_deleted=False).update(status="failed")
        DeploymentLog.objects.create(deployment=d,level="error",message=message)

def run_worker(proc=None):
    proc=proc or get_background_processor()
    if proc.name!="sqlite":raise RuntimeError("Select WEBOPS_BG_PROCESSOR=sqlite")
    stop=threading.Event()
    def stop_signal(*_):stop.set()
    signal.signal(signal.SIGTERM,stop_signal)
    signal.signal(signal.SIGINT,stop_signal)
    with proc.path.with_suffix(".worker.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for job in proc.interrupted():
            close_old_connections()
            record_failure(job,"Background worker interrupted this operation. Inspect process state and logs before retrying; work was not automatically replayed.")
            proc.finish(job["id"],error="Interrupted worker; manual reconciliation required")
        proc.prune()
        proc.heartbeat()
        def pulse():
            while not stop.wait(3):
                try:proc.heartbeat()
                except Exception:logger.warning("Queue heartbeat failed")
        thread=threading.Thread(target=pulse,daemon=True);thread.start()
        try:
            while not stop.is_set():
                job=proc.claim()
                if not job:
                    stop.wait(.25);continue
                close_old_connections()
                try:
                    p=json.loads(job["payload"])
                    result=proc.registry[job["task"]](*p["args"],**p["kwargs"])
                    if isinstance(result,dict) and result.get("success") is False:
                        raise RuntimeError("Task reported failure")
                    proc.finish(job["id"],value=result)
                except Exception:
                    logger.warning("Queue task failed id=%s task=%s",job["id"],job["task"])
                    record_failure(job,"Background operation failed. Inspect deployment logs and current runtime state before retrying.")
                    proc.finish(job["id"],error="Background operation failed; inspect deployment logs")
                finally:close_old_connections()
        finally:
            stop.set()
            thread.join(timeout=5)
            with proc.connection() as db:db.execute("DELETE FROM worker WHERE id=1")
