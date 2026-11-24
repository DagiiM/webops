from unittest.mock import Mock,patch
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.urls import reverse
import requests
from apps.deployments.services.llm_preflight import SUPPORTED

@override_settings(WEBOPS_RUNTIME="supervisor",WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL=True)
class CatalogTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user(username="catalog-user")
        self.url=reverse("deployments:llm_search")
        self.client.force_login(self.user)
    def test_default_catalog_loads_pinned_metadata(self):
        def response(url,**kwargs):
            for model,revision in SUPPORTED.items():
                if url.endswith("/"+model+"/revision/"+revision):
                    r=Mock();r.json.return_value={"id":model,"sha":revision,"pipeline_tag":"text-generation","safetensors":{"total":123},"downloads":5}
                    return r
            raise AssertionError("Unexpected URL")
        with patch("apps.deployments.services.llm_catalog.requests.get",side_effect=response) as get:
            data=self.client.get(self.url).json()
            self.assertEqual({m["id"] for m in data["models"]},set(SUPPORTED))
            self.assertTrue(all(m["reviewed"] for m in data["models"]))
            self.assertEqual(get.call_count,2)
            self.client.get(self.url)
            self.assertEqual(get.call_count,2)
    def test_search_filters_private_gated_and_unsupported_task(self):
        model=next(iter(SUPPORTED))
        payload=[{"id":"public/model","pipeline_tag":"text-generation","tags":["safetensors"]},
                 {"id":model,"pipeline_tag":"text-generation"},
                 {"id":"private/model","pipeline_tag":"text-generation","private":True},
                 {"id":"gated/model","pipeline_tag":"text-generation","gated":"manual"},
                 {"id":"image/model","pipeline_tag":"image-text-to-text"},
                 {"id":"../bad","pipeline_tag":"text-generation"}]
        with patch("apps.deployments.services.llm_catalog.requests.get") as get:
            get.return_value.json.return_value=payload
            r=self.client.get(self.url,{"q":"test"})
            self.assertEqual(r.status_code,200)
            self.assertEqual([m["id"] for m in r.json()["models"]],[model,"public/model"])
            self.assertFalse(r.json()["models"][1]["reviewed"])
            self.assertEqual(get.call_args.kwargs["params"]["limit"],12)
            self.assertFalse(get.call_args.kwargs["allow_redirects"])
    def test_unavailable_and_invalid(self):
        with patch("apps.deployments.services.llm_catalog.requests.get",side_effect=requests.Timeout):
            self.assertEqual(self.client.get(self.url,{"q":"qwen"}).status_code,503)
        self.assertEqual(self.client.get(self.url,{"q":"x"*101}).status_code,400)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)
    def test_portable_page_contains_catalog(self):
        r=self.client.get(reverse("deployments:llm_create"))
        self.assertContains(r,"Discover models from Hugging Face")
        self.assertContains(r,"hfCatalogResults")
