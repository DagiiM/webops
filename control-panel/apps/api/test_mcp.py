import hashlib,json,secrets
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from unittest.mock import patch
from apps.api.models import MCPAccessToken
from apps.deployments.models import ApplicationDeployment, DeploymentLog

@override_settings(WEBOPS_RUNTIME="supervisor",WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL=True,
 CHANNEL_LAYERS={"default":{"BACKEND":"channels.layers.InMemoryChannelLayer"}})
class MCPTests(TestCase):
    def setUp(self):
        cache.clear()
        U=get_user_model()
        self.owner=U.objects.create_user(username="mcp-owner")
        self.other=U.objects.create_user(username="mcp-other")
        self.d=ApplicationDeployment.objects.create(name="mcp-owned",repo_url="https://github.com/example/repo",deployed_by=self.owner,status="requested")
        self.foreign=ApplicationDeployment.objects.create(name="mcp-foreign",repo_url="https://github.com/example/repo",deployed_by=self.other)
        self.raw="wops_mcp_"+secrets.token_urlsafe(32)
        self.token=MCPAccessToken.objects.create(user=self.owner,name="test",digest=hashlib.sha256(self.raw.encode()).hexdigest(),expires_at=timezone.now()+timezone.timedelta(days=1))
    def rpc(self,method,params=None,auth=True,**headers):
        return self.client.post("/api/mcp/",{"jsonrpc":"2.0","id":1,"method":method,"params":params or {}},content_type="application/json",secure=True,
            HTTP_AUTHORIZATION="Bearer "+self.raw if auth else "",HTTP_MCP_PROTOCOL_VERSION="2025-11-25",**headers)
    def call(self,name,args=None):
        return self.rpc("tools/call",{"name":name,"arguments":args or {}}).json()
    def test_auth_and_origin(self):
        self.assertEqual(self.rpc("tools/list",auth=False).status_code,401)
        self.assertEqual(self.rpc("tools/list",HTTP_ORIGIN="https://evil.invalid").status_code,403)
        self.assertEqual(self.rpc("tools/list").status_code,200)
    def test_initialize_list_read_only(self):
        r=self.rpc("initialize",{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1"}}).json()
        self.assertEqual(r["result"]["protocolVersion"],"2025-11-25")
        names={t["name"] for t in self.rpc("tools/list").json()["result"]["tools"]}
        self.assertIn("check_model",names);self.assertNotIn("deploy_model",names)
        self.assertIn("error",self.call("control_deployment",{"deployment_id":self.d.pk,"action":"cancel_request","confirm":True}))
    def test_ownership_and_redaction(self):
        data=self.call("list_deployments")["result"]["structuredContent"]
        self.assertEqual([d["id"] for d in data["deployments"]],[self.d.pk])
        self.assertTrue(self.call("get_deployment",{"deployment_id":self.foreign.pk})["result"]["isError"])
        DeploymentLog.objects.create(deployment=self.d,message="password=example-sensitive-value")
        r=self.call("get_deployment_logs",{"deployment_id":self.d.pk})["result"]
        self.assertNotIn("example-sensitive-value",json.dumps(r))
    def test_control_requires_explicit_consent_and_owner(self):
        self.token.can_control=True;self.token.save()
        self.assertTrue(self.call("control_deployment",{"deployment_id":self.d.pk,"action":"cancel_request","confirm":False})["result"]["isError"])
        self.assertTrue(self.call("control_deployment",{"deployment_id":self.foreign.pk,"action":"cancel_request","confirm":True})["result"]["isError"])
        self.assertFalse(self.call("control_deployment",{"deployment_id":self.d.pk,"action":"cancel_request","confirm":True})["result"]["isError"])
        self.d.refresh_from_db();self.assertTrue(self.d.is_deleted)
    def test_create_review_request_without_executing(self):
        self.token.can_control=True;self.token.save()
        with patch("apps.core.security.access.queue_deployment") as queue:
            r=self.call("request_application",{"name":"mcp-new","repository":"https://github.com/example/repo","confirm":True})
            self.assertFalse(r["result"]["isError"]);queue.assert_not_called()
        self.assertEqual(ApplicationDeployment.objects.get(name="mcp-new").status,"requested")
    def test_expired_revoked_inactive(self):
        self.token.revoked_at=timezone.now();self.token.save()
        self.assertEqual(self.rpc("tools/list").status_code,401)
        self.token.revoked_at=None;self.token.expires_at=timezone.now();self.token.save()
        self.assertEqual(self.rpc("tools/list").status_code,401)
    def test_token_management_and_revoke(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/mcp/access/",secure=True).status_code,200)
        r=self.client.post("/api/mcp/access/",{"name":"test-client"},secure=True)
        self.assertEqual(r.status_code,200)
        token=MCPAccessToken.objects.get(name="test-client")
        self.assertFalse(token.can_control)
        self.assertNotIn(token.digest,r.content.decode())
        self.assertEqual(self.client.post(f"/api/mcp/access/{token.pk}/revoke/",secure=True).status_code,302)
        token.refresh_from_db();self.assertIsNotNone(token.revoked_at)
    def test_invalid_schema_notification(self):
        self.assertTrue(self.call("list_deployments",{"limit":True})["result"]["isError"])
        r=self.client.post("/api/mcp/",{"jsonrpc":"2.0","method":"notifications/initialized"},content_type="application/json",secure=True,HTTP_AUTHORIZATION="Bearer "+self.raw)
        self.assertEqual(r.status_code,202)
