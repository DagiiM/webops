"""Current-route database integration tests.

Replaces legacy class-based view imports removed from application routes.
Retains all sixteen original scenario names and adds ownership regression cases.
Uses Django test client and real encrypted fixtures; no cases are skipped.
"""
from unittest.mock import patch, ANY
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from apps.databases.models import Database
from apps.databases.forms import DatabaseForm
from apps.deployments.models import ApplicationDeployment
from apps.core.utils import encrypt_password, decrypt_password


class DatabaseViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dbowner', password='secure-password-1')
        self.other = User.objects.create_user(username='otheruser', password='secure-password-2')
        self.deployment = ApplicationDeployment.objects.create(
            name='owned-db-test-app', repo_url='https://example.invalid/repo.git',
            branch='main', deployed_by=self.user)
        self.db = Database.objects.create(
            name='test_db', db_type='postgresql', host='localhost', port=5432,
            username='test_user', password=encrypt_password('test_password'),
            database_name='test_db', deployment=self.deployment, created_by=self.user)
        self.client.force_login(self.user)

    def url(self, name, pk=False):
        return reverse(name, args=[self.db.pk] if pk else None)

    @staticmethod
    def form_data(**changes):
        data = {'name':'new_db','db_type':'postgresql','host':'localhost',
                'port':5432,'username':'new_user','password':'new_password',
                'database_name':'new_db'}
        data.update(changes)
        return data

    def test_database_list_view(self):
        response = self.client.get(self.url('database_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')

    def test_database_detail_view(self):
        response = self.client.get(self.url('database_detail', True))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')
        self.assertContains(response, 'test_user')
        self.assertContains(response, 'localhost')

    def test_database_create_view_get(self):
        response = self.client.get(self.url('database_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], DatabaseForm)

    def test_database_create_view_post_valid(self):
        response = self.client.post(self.url('database_create'), data=self.form_data())
        self.assertEqual(response.status_code, 302, response.content[:120])
        self.assertEqual(response.url, self.url('database_list'))
        obj = Database.objects.get(name='new_db')
        self.assertEqual(obj.created_by, self.user)
        self.assertNotEqual(obj.password, 'new_password')
        self.assertEqual(decrypt_password(obj.password), 'new_password')

    def test_database_create_view_post_invalid(self):
        response = self.client.post(self.url('database_create'),
                                    self.form_data(name='invalid@name'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Database.objects.filter(name='invalid@name').exists())
        self.assertIn('name', response.context['form'].errors)

    def test_database_update_view_get(self):
        response = self.client.get(self.url('database_update', True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].instance.pk, self.db.pk)

    def test_database_update_view_post_valid(self):
        response = self.client.post(self.url('database_update', True),
                                    data=self.form_data(name='updated_db',
                                        database_name='updated_db',host='updated_host',
                                        port=5433, username='updated_user',
                                        password='updated_password'))
        self.assertEqual(response.status_code, 302, response.content[:120])
        self.db.refresh_from_db()
        self.assertEqual(self.db.name, 'updated_db')
        self.assertEqual(self.db.username, 'updated_user')
        self.assertEqual(decrypt_password(self.db.password), 'updated_password')

    def test_database_update_view_post_invalid(self):
        response = self.client.post(self.url('database_update', True),
                                    data=self.form_data(name='invalid@name'))
        self.assertEqual(response.status_code, 200)
        self.db.refresh_from_db()
        self.assertEqual(self.db.name, 'test_db')
        self.assertIn('name', response.context['form'].errors)

    def test_database_delete_view_get(self):
        response = self.client.get(self.url('database_delete', True))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')

    @patch('apps.databases.views.DatabaseService')
    def test_database_delete_view_post_confirm(self, service):
        service.return_value.delete_database.return_value = (True, 'deleted')
        service.return_value.delete_user.return_value = (True, 'removed')
        response = self.client.post(self.url('database_delete', True), {'confirm':'yes'})
        self.assertEqual(response.status_code, 302, response.content[:120])
        self.assertEqual(response.url, self.url('database_list'))
        service.return_value.delete_database.assert_called_once_with('test_db')
        service.return_value.delete_user.assert_called_once_with('test_user')
        self.db.refresh_from_db()
        self.assertTrue(self.db.is_deleted)

    @patch('apps.databases.views.DatabaseService')
    def test_database_delete_view_post_no_confirm(self, service):
        response = self.client.post(self.url('database_delete', True), {'confirm':'no'})
        self.assertEqual(response.status_code, 400)
        service.assert_not_called()
        self.db.refresh_from_db()
        self.assertFalse(self.db.is_deleted)

    def test_database_credentials_view_html(self):
        # The currently supported credential endpoint is JSON, not legacy HTML.
        response = self.client.get(self.url('database_credentials_json', True))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        self.assertEqual(response.json()['password'], 'test_password')

    def test_database_credentials_view_json(self):
        response = self.client.get(self.url('database_credentials_json', True),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        record = response.json()
        self.assertEqual(record['name'], 'test_db')
        self.assertEqual(record['username'], 'test_user')
        self.assertEqual(record['password'], 'test_password')
        self.assertEqual(record['host'], 'localhost')
        self.assertEqual(record['port'], 5432)
        self.assertEqual(record['connection_string'],
                         'postgresql://test_user:test_password@localhost:5432/test_db')

    def test_database_credentials_view_masked(self):
        # General business pages must not expose plaintext or encrypted passwords.
        response = self.client.get(self.url('database_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'test_password')
        self.assertNotContains(response, self.db.password)

    @patch('apps.databases.views.logger')
    def test_database_credentials_view_logging(self, logger):
        response = self.client.get(self.url('database_credentials_json', True))
        self.assertEqual(response.status_code, 200)
        logger.info.assert_any_call(
            'Database credentials accessed via JSON API',
            extra={'user_id':self.user.pk,'username':self.user.username,
                   'database_id':self.db.pk,'database_name':'test_db',
                   'timestamp':ANY})

    def test_database_views_require_login(self):
        self.client.logout()
        for name,detail in (('database_list',False),('database_create',False),
                            ('database_detail',True),('database_update',True),
                            ('database_delete',True),('database_credentials_json',True)):
            with self.subTest(name=name):
                response = self.client.get(self.url(name,detail))
                self.assertEqual(response.status_code,302)
                self.assertIn('/auth/login/',response.url)

    def test_other_user_cannot_read_credentials(self):
        self.client.force_login(self.other)
        for name in ('database_detail','database_credentials_json','database_update'):
            with self.subTest(name=name):
                response = self.client.get(self.url(name,True))
                self.assertEqual(response.status_code,404)

    @patch('apps.databases.views.DatabaseService')
    def test_other_user_cannot_delete_database(self, service):
        self.client.force_login(self.other)
        response=self.client.post(self.url('database_delete',True),{'confirm':'yes'})
        self.assertEqual(response.status_code,404)
        service.assert_not_called()
        self.db.refresh_from_db()
        self.assertFalse(self.db.is_deleted)

    def test_standalone_database_visible_only_to_creator(self):
        Database.objects.create(name='standalone_owned',db_type='postgresql',
            host='localhost',port=5432,username='standalone_user',
            database_name='standalone_owned',password=encrypt_password('test_password'),
            created_by=self.user)
        self.assertContains(self.client.get(self.url('database_list')),'standalone_owned')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url('database_list')),'standalone_owned')
