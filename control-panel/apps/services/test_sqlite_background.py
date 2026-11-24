from tempfile import TemporaryDirectory
from pathlib import Path
from django.test import SimpleTestCase
from apps.services.background.sqlite_adapter import SQLiteBackgroundProcessor
from apps.services.background.interface import TaskStatus

class DurableQueueTests(SimpleTestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"jobs.sqlite3"
        self.registry={"deploy":lambda pk:{"success":True,"id":pk}}
        self.q=SQLiteBackgroundProcessor(self.path,self.registry)
    def test_persistence_and_duplicate_submission(self):
        h=self.q.submit("deploy",1)
        q=SQLiteBackgroundProcessor(self.path,self.registry)
        self.assertEqual(q.status(h),TaskStatus.PENDING)
        self.assertEqual(q.submit("deploy",1).id,h.id)
        job=q.claim()
        self.assertEqual(job["id"],h.id)
        q.finish(h.id,{"success":True})
        self.assertEqual(self.q.result(h,timeout=1),{"success":True})
    def test_interruption_not_replayed(self):
        h=self.q.submit("deploy",1)
        self.q.claim()
        q=SQLiteBackgroundProcessor(self.path,self.registry)
        self.assertEqual(q.interrupted()[0]["id"],h.id)
        q.finish(h.id,error="Interrupted")
        self.assertIsNone(q.claim())
        with self.assertRaises(RuntimeError):q.result(h,timeout=1)
    def test_revoke_pending_only(self):
        h=self.q.submit("deploy",1)
        self.assertTrue(self.q.revoke(h))
        self.assertEqual(self.q.status(h),TaskStatus.REVOKED)
        self.assertIsNone(self.q.claim())
        h=self.q.submit("deploy",2);self.q.claim()
        self.assertFalse(self.q.revoke(h))
    def test_validation_and_heartbeat(self):
        self.assertFalse(self.q.healthcheck())
        self.q.heartbeat()
        self.assertTrue(self.q.healthcheck())
        for task,args in [("unknown",(1,)),("deploy",("1",)),("deploy",(True,)),("deploy",())]:
            with self.assertRaises(ValueError):self.q.submit(task,*args)
