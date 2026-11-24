import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from apps.deployments.models import ApplicationDeployment
from apps.services.runtime.policy import application_allowed, restricted
from apps.services.runtime.sandbox import available
from apps.core.security.access import queue_deployment

@override_settings(WEBOPS_RUNTIME="supervisor",WEBOPS_WORKLOAD_POLICY="restricted",CHANNEL_LAYERS={"default":{"BACKEND":"channels.layers.InMemoryChannelLayer"}})
class RestrictedPolicyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user(username="restricted-owner",is_staff=True)
        self.client.force_login(self.user)
    def test_staff_cannot_approve_executable(self):
        d=ApplicationDeployment.objects.create(name="restricted-request",repo_url="https://github.com/example/repo",deployed_by=self.user,status="requested")
        self.assertFalse(application_allowed(d))
        with patch("apps.deployments.views.application_deployment.queue_deployment") as queue:
            r=self.client.post(reverse("deployments:deployment_approve",args=[d.pk]))
            self.assertEqual(r.status_code,403)
            queue.assert_not_called()
        d.refresh_from_db()
        self.assertEqual(d.status,"requested")
    def test_queue_refuses_direct_executable_submission(self):
        d=ApplicationDeployment.objects.create(name="restricted-executable",repo_url="https://github.com/example/repo",deployed_by=self.user,status="pending")
        with self.assertRaisesRegex(ValueError,"isolated worker"):
            queue_deployment(d)
    def test_staff_creation_preserves_request_without_build(self):
        with patch("apps.deployments.views.application_deployment.queue_deployment") as queue:
            self.assertEqual(self.client.post(reverse("deployments:deployment_create"),{"name":"restricted-build","repo_url":"https://github.com/example/repo","branch":"main"}).status_code,302)
            self.assertEqual(ApplicationDeployment.objects.get(name="restricted-build").status,"requested")
            queue.assert_not_called()
    def test_static_publication_allowed(self):
        d=ApplicationDeployment.objects.create(name="restricted-static",repo_url="https://github.com/example/repo",deployed_by=self.user,static_only=True)
        self.assertTrue(application_allowed(d))
    def test_no_build_before_clone(self):
        from apps.deployments.services import DeploymentService
        d=ApplicationDeployment.objects.create(name="restricted-direct",repo_url="https://github.com/example/repo",deployed_by=self.user,status="pending")
        s=DeploymentService()
        with patch.object(s,"clone_repository") as clone:
            success,error=s.prepare_deployment(d)
            self.assertFalse(success);self.assertIn("isolated worker",error);clone.assert_not_called()

class KernelConfinementTests(SimpleTestCase):
    def test_canary_files_and_outbound_connections(self):
        if not available():self.skipTest("Landlock ABI 4/libseccomp not available on this test host")
        with TemporaryDirectory() as root:
            root=Path(root)
            allowed=root/"published";allowed.mkdir()
            (allowed/"index.html").write_text("allowed")
            forbidden=root/"control-plane-canary.txt";forbidden.write_text("private")
            script=root/"probe.py"
            script.write_text('''import os,socket,sys
from pathlib import Path
public=Path(sys.argv[1]);secret=Path(sys.argv[2])
assert (public/"index.html").read_text()=="allowed"
def denied(fn):
    try:fn()
    except PermissionError:return
    raise AssertionError("operation unexpectedly permitted")
denied(lambda:secret.read_text())
denied(lambda:secret.write_text("changed"))
denied(lambda:(public/"new.html").write_text("changed"))
s=socket.socket()
denied(lambda:s.connect(("127.0.0.1",int(sys.argv[3]))))
s.close()
s=socket.socket()
denied(lambda:s.bind(("127.0.0.1",int(sys.argv[3]))))
s.close()
denied(lambda:socket.socket(socket.AF_UNIX))
denied(lambda:socket.socket(socket.AF_INET,socket.SOCK_DGRAM))
denied(lambda:os.kill(os.getppid(),0))
print("PASS canary read/write, asset write, outbound TCP/UNIX/UDP, and process signal denied")
''')
            # Reserve an unrelated local port; only the workload's own bind is permitted.
            import socket
            with socket.socket() as listener:
                listener.bind(("127.0.0.1",0));listener.listen()
                unrelated=listener.getsockname()[1]
                profile={"read":[str(allowed),str(script)],"write":[],"executable":sys.executable,"port":18599}
                import json
                launcher=Path(__file__).parent/"runtime"/"launcher.py"
                spec=root/"spec.json"
                spec.write_text(json.dumps({"cwd":str(allowed),"argv":[sys.executable,str(script),str(allowed),str(forbidden),str(unrelated)],"env":{"PATH":"/usr/local/bin:/usr/bin:/bin","LANG":"C.UTF-8"},"sandbox":profile}))
                proc=subprocess.run([sys.executable,str(launcher),str(spec)],capture_output=True,text=True,timeout=10)
                self.assertEqual(proc.returncode,0,proc.stderr)
                self.assertIn("PASS canary",proc.stdout)
                self.assertEqual(forbidden.read_text(),"private")
