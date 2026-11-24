from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.core.common.utils.validators import normalize_github_repo_url, parse_github_repo
from apps.deployments.models import ApplicationDeployment


class ParseGithubRepoTests(SimpleTestCase):
    CANON = "https://github.com/ifinsta/ifinsta"

    def test_every_common_spelling_normalises_to_the_same_url(self):
        for raw in [
            "https://github.com/ifinsta/ifinsta", "https://github.com/ifinsta/ifinsta/", "https://github.com/ifinsta/ifinsta.git",
            "http://github.com/ifinsta/ifinsta", "https://www.github.com/ifinsta/ifinsta", "github.com/ifinsta/ifinsta",
            "ifinsta/ifinsta", "  https://github.com/ifinsta/ifinsta  ", "https://github.com/ifinsta/ifinsta?tab=readme#top",
            "https://github.com/ifinsta/ifinsta/tree/main", "https://github.com/ifinsta/ifinsta/issues",
        ]:
            self.assertEqual(normalize_github_repo_url(raw), self.CANON, raw)

    def test_branch_comes_only_from_a_tree_url(self):
        self.assertEqual(parse_github_repo("https://github.com/o/r/tree/feature/x")["branch"], "feature/x")
        self.assertIsNone(parse_github_repo("https://github.com/o/r")["branch"])
        self.assertIsNone(parse_github_repo("https://github.com/o/r/blob/main/README.md")["branch"])

    def test_ssh_is_kept_as_typed(self):
        parsed = parse_github_repo("git@github.com:ifinsta/ifinsta.git")
        self.assertTrue(parsed["ssh"])
        self.assertEqual(parsed["url"], "git@github.com:ifinsta/ifinsta.git")
        self.assertEqual((parsed["owner"], parsed["repo"]), ("ifinsta", "ifinsta"))

    def test_rejects_other_hosts_and_junk(self):
        for raw in ["", "   ", None, "https://gitlab.com/o/r", "https://example.com/o/r", "ftp://github.com/o/r",
                    "just-a-word", "o/", "/o/r/extra/stuff", "https://github.com/o", "has space/repo", "o/r r",
                    "https://github.com/../r", "https://github.com/o/..", "https://github.com/-bad/r",
                    "javascript:alert(1)", "x" * 500]:
            self.assertIsNone(normalize_github_repo_url(raw), repr(raw))

    def test_tree_branch_with_traversal_is_ignored(self):
        self.assertIsNone(parse_github_repo("https://github.com/o/r/tree/a/../b")["branch"])


@override_settings(WEBOPS_RUNTIME="supervisor", WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL=True,
                   CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class CreateFormTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="form-user")
        self.client.force_login(self.user)
        self.url = reverse("deployments:deployment_create")

    def post(self, **data):
        base = {"name": "my-app", "repo_url": "https://github.com/ifinsta/ifinsta", "branch": "main", "domain": ""}
        base.update(data)
        with patch("apps.deployments.views.application_deployment.queue_deployment"):
            return self.client.post(self.url, base)

    def test_pasted_variants_are_accepted_and_stored_canonically(self):
        for i, raw in enumerate(["https://github.com/ifinsta/ifinsta/", "ifinsta/ifinsta", "github.com/ifinsta/ifinsta",
                                 "https://github.com/ifinsta/ifinsta/tree/main"]):
            r = self.post(name=f"app-{i}", repo_url=raw)
            self.assertEqual(r.status_code, 302, raw)
            self.assertEqual(ApplicationDeployment.objects.get(name=f"app-{i}").repo_url, "https://github.com/ifinsta/ifinsta")

    def test_branch_is_taken_from_a_tree_url_unless_one_was_chosen(self):
        self.post(name="a1", repo_url="https://github.com/ifinsta/ifinsta/tree/develop", branch="main")
        self.assertEqual(ApplicationDeployment.objects.get(name="a1").branch, "develop")
        self.post(name="a2", repo_url="https://github.com/ifinsta/ifinsta/tree/develop", branch="release")
        self.assertEqual(ApplicationDeployment.objects.get(name="a2").branch, "release")

    def test_missing_name_is_filled_from_the_repository(self):
        r = self.post(name="", repo_url="https://github.com/ifinsta/my-service")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ApplicationDeployment.objects.filter(name="my-service").exists())

    def test_rejection_rerenders_the_form_with_values_and_a_persistent_error(self):
        r = self.post(name="keep-me", repo_url="https://gitlab.com/o/r", domain="example.com")
        self.assertEqual(r.status_code, 400)
        html = r.content.decode()
        self.assertIn("ui-formerror", html)
        self.assertIn("does not look like a GitHub repository", html)
        self.assertIn('value="keep-me"', html)
        self.assertIn('value="https://gitlab.com/o/r"', html)
        self.assertIn('value="example.com"', html)
        self.assertFalse(ApplicationDeployment.objects.filter(name="keep-me").exists())

    def test_each_validation_failure_explains_itself(self):
        ApplicationDeployment.objects.create(name="taken", repo_url="https://github.com/a/b", deployed_by=self.user)
        cases = [({"repo_url": ""}, "Enter the repository URL"), ({"name": "taken"}, "already exists"),
                 ({"domain": "not a domain"}, "Invalid domain"), ({"name": "@@@"}, "Invalid deployment name")]
        for data, expected in cases:
            r = self.post(**data)
            self.assertEqual(r.status_code, 400, data)
            self.assertIn(expected, r.content.decode(), data)

    def test_repo_input_is_not_a_browser_url_field(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('type="url" id="repo_url"', html)
        self.assertIn('id="repo_url"', html)
