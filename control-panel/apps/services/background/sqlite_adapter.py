"""Durable single-host queue. Interrupted work is failed, never silently replayed."""
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .interface import TaskHandle, TaskStatus

class SQLiteBackgroundProcessor:
    name = "sqlite"
    def __init__(self, path, registry):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self.registry = registry
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL,
              state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
              result TEXT, error TEXT
            );
            CREATE INDEX IF NOT EXISTS jobs_state_created ON jobs(state,created);
            CREATE TABLE IF NOT EXISTS worker (id INTEGER PRIMARY KEY CHECK(id=1), heartbeat REAL NOT NULL);
            """)
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path, timeout=15)
        db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def submit(self, task_name, *args, **kwargs):
        if task_name not in self.registry:
            raise ValueError("Unknown background task")
        # The portable queue accepts only registered deployment/service operations.
        if len(args)!=1 or type(args[0]) is not int or args[0]<1 or kwargs:
            raise ValueError("Expected one deployment ID")
        payload=json.dumps({"args":args,"kwargs":kwargs},separators=(",",":"))
        now=time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            same=db.execute("SELECT id FROM jobs WHERE task=? AND payload=? AND state IN ('pending','started')",(task_name,payload)).fetchone()
            if same:return TaskHandle(same["id"],self.name,task_name)
            if db.execute("SELECT count(*) FROM jobs WHERE state IN ('pending','started')").fetchone()[0]>=100:
                raise RuntimeError("Background queue is full")
            ident=uuid.uuid4().hex
            db.execute("INSERT INTO jobs(id,task,payload,state,created,updated) VALUES(?,?,?,'pending',?,?)",(ident,task_name,payload,now,now))
        return TaskHandle(ident,self.name,task_name)

    def status(self, handle):
        with self.connection() as db:
            row=db.execute("SELECT state FROM jobs WHERE id=?",(handle.id,)).fetchone()
        return TaskStatus(row["state"]) if row else TaskStatus.UNKNOWN

    def result(self,handle,timeout=None):
        until=None if timeout is None else time.monotonic()+timeout
        while True:
            with self.connection() as db:
                row=db.execute("SELECT state,result,error FROM jobs WHERE id=?",(handle.id,)).fetchone()
            if not row:raise ValueError("Unknown task")
            if row["state"]=="success":return json.loads(row["result"])
            if row["state"] in ("failed","revoked"):raise RuntimeError(row["error"] or row["state"])
            if until is not None and time.monotonic()>=until:raise TimeoutError("Task result timeout")
            time.sleep(.1)

    def revoke(self,handle,terminate=False):
        with self.connection() as db:
            return bool(db.execute("UPDATE jobs SET state='revoked',updated=?,error='Cancelled before execution' WHERE id=? AND state='pending'",(time.time(),handle.id)).rowcount)

    def heartbeat(self):
        with self.connection() as db:
            db.execute("INSERT INTO worker(id,heartbeat) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat",(time.time(),))

    def healthcheck(self):
        with self.connection() as db:
            row=db.execute("SELECT heartbeat FROM worker WHERE id=1").fetchone()
        return bool(row and 0<=time.time()-row[0]<15)

    def backend_info(self):
        return {"type":"sqlite","durable_on_disk":True,"worker_ready":self.healthcheck(),"registry_size":len(self.registry)}

    def get_status(self):
        with self.connection() as db:
            counts=dict(db.execute("SELECT state,count(*) FROM jobs GROUP BY state").fetchall())
        healthy=self.healthcheck()
        return {"processor":self.name,"status":"healthy" if healthy else "unavailable","healthy":healthy,
                "active_tasks":counts.get("started",0),"queued_tasks":counts.get("pending",0),
                "total_tasks":sum(counts.values()),"pending_tasks":counts.get("pending",0),
                "running_tasks":counts.get("started",0),"completed_tasks":counts.get("success",0),
                "failed_tasks":counts.get("failed",0),"backend_info":self.backend_info()}

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM jobs WHERE state='pending' ORDER BY created,id LIMIT 1").fetchone()
            if row:db.execute("UPDATE jobs SET state='started',updated=? WHERE id=?",(time.time(),row["id"]))
        return dict(row) if row else None

    def finish(self,job_id,value=None,error=None):
        with self.connection() as db:
            db.execute("UPDATE jobs SET state=?,result=?,error=?,updated=? WHERE id=? AND state='started'",
                       ("failed" if error else "success",None if error else json.dumps(value),error,time.time(),job_id))

    def interrupted(self):
        with self.connection() as db:
            rows=db.execute("SELECT * FROM jobs WHERE state='started'").fetchall()
        return [dict(row) for row in rows]

    def prune(self):
        # Keep a bounded operational history; never remove pending/in-flight work.
        with self.connection() as db:
            db.execute("DELETE FROM jobs WHERE state IN ('success','failed','revoked') AND updated<?",(time.time()-30*86400,))
