import hashlib
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.deployments.models import WorkerNode
from apps.deployments.services import worker_queue


class RegisterWorkerTests(TestCase):
    def digest(self, token):
        return hashlib.sha256(token.encode()).hexdigest()

    def test_registered_worker_authenticates_with_the_token_it_generated(self):
        token = worker_queue.TOKEN_PREFIX + "x" * 43
        call_command("register_worker", "--name", "pod-worker", "--digest", self.digest(token), stdout=StringIO())
        node = worker_queue.authenticate(token)
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "pod-worker")

    def test_rekeying_replaces_the_token_and_clears_revocation(self):
        old, new = worker_queue.TOKEN_PREFIX + "a" * 43, worker_queue.TOKEN_PREFIX + "b" * 43
        call_command("register_worker", "--name", "w1", "--digest", self.digest(old), stdout=StringIO())
        node = WorkerNode.objects.get(name="w1")
        worker_queue.revoke(node)
        call_command("register_worker", "--name", "w1", "--digest", self.digest(new), stdout=StringIO())
        self.assertIsNone(worker_queue.authenticate(old))
        self.assertIsNotNone(worker_queue.authenticate(new))

    def test_bad_input_is_refused(self):
        for digest in ("short", "z" * 64, "A" * 10):
            with self.assertRaises(CommandError):
                call_command("register_worker", "--name", "w1", "--digest", digest)
        with self.assertRaises(CommandError):
            call_command("register_worker", "--name", "bad/name", "--digest", "a" * 64)

    def test_one_token_cannot_serve_two_workers(self):
        call_command("register_worker", "--name", "w1", "--digest", "c" * 64, stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("register_worker", "--name", "w2", "--digest", "c" * 64)
