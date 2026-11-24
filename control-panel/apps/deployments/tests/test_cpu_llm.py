from unittest.mock import patch, Mock
from tempfile import TemporaryDirectory
from pathlib import Path
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from apps.deployments.models import LLMDeployment
from apps.deployments.services.llm_preflight import check_model, SUPPORTED

@override_settings(WEBOPS_RUNTIME="supervisor", WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL=True,
 CHANNEL_LAYERS={"default":{"BACKEND":"channels.layers.InMemoryChannelLayer"}})
class CPUModelPreflightTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user(username="model-owner")
        self.client.force_login(self.user)
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        Path(self.temp.name,".ready").touch()
        self.settings=override_settings(WEBOPS_CPU_LLM_ENV=self.temp.name,WEBOPS_INSTALL_PATH=self.temp.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        h=patch("apps.deployments.services.llm_preflight.hardware",return_value={"ram_gb":8,"available_ram_gb":5,"disk_gb":19,"cpu_count":2,"device":"CPU","runtime":"supervisor"})
        h.start();self.addCleanup(h.stop)
        p=patch("apps.deployments.services.llm_preflight.portable_runtime",return_value=Mock(ready=lambda:True))
        p.start();self.addCleanup(p.stop)
        self.model="HuggingFaceTB/SmolLM2-135M-Instruct"
        self.metadata=Mock(status_code=200)
        self.metadata.json.return_value={"sha":SUPPORTED[self.model],"pipeline_tag":"text-generation","safetensors":{"total":134515008,"parameters":{"BF16":134515008}}}
        h=patch("apps.deployments.services.llm_preflight.requests.get",return_value=self.metadata)
        h.start();self.addCleanup(h.stop)
    def test_compatible_model(self):
        self.assertTrue(check_model(self.model)["success"])
    def test_large_model_rejected(self):
        self.metadata.json.return_value={"pipeline_tag":"image-text-to-text","safetensors":{"total":266000000000,"parameters":{"BF16":266000000000}}}
        data=check_model("thinkingmachines/Inkling-Small")
        self.assertFalse(data["success"])
        self.assertTrue(any("Insufficient storage" in e for e in data["errors"]))
    def test_incompatible_create_does_not_create_record(self):
        r=self.client.post(reverse("deployments:llm_create"),{"name":"bad-model","model_name":"unknown/model"})
        self.assertEqual(r.status_code,400)
        self.assertFalse(LLMDeployment.objects.filter(name="bad-model").exists())
    def test_user_can_check_model(self):
        r=self.client.post(reverse("deployments:llm_detect"),{"model_name":self.model})
        self.assertEqual(r.status_code,200)
        self.assertTrue(r.json()["success"])
    def test_slot_reserved(self):
        LLMDeployment.objects.create(name="reserved-model",model_name=self.model,deployed_by=self.user,status="building")
        self.assertFalse(check_model(self.model)["success"])
    def test_owner_inference_and_cross_user_denial(self):
        d=LLMDeployment.objects.create(name="running-model",model_name=self.model,deployed_by=self.user,status="running",port=9010)
        response=Mock(status_code=200)
        response.json.return_value={"choices":[{"text":"generated"}]}
        with patch("requests.post",return_value=response):
            r=self.client.post(reverse("deployments:llm_test",args=[d.pk]),{"prompt":"Hello","max_tokens":8},content_type="application/json")
            self.assertEqual(r.status_code,200);self.assertEqual(r.json()["response"],"generated")
        self.client.force_login(get_user_model().objects.create_user(username="another"))
        self.assertEqual(self.client.post(reverse("deployments:llm_test",args=[d.pk]),{},content_type="application/json").status_code,404)
