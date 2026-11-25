import unittest
from unittest.mock import patch

from ponto_apoio import create_app


class SecurityTests(unittest.TestCase):
    def setUp(self):
        with patch('ponto_apoio.init_database'):
            self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_post_requires_session_token(self):
        self.assertEqual(self.client.post('/students', data={'full_name': 'Ana'}).status_code, 400)
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'valid-token'
        self.assertEqual(self.client.post('/students', data={'_csrf_token': 'wrong'}).status_code, 400)
        response = self.client.post('/students', data={'_csrf_token': 'valid-token', 'full_name': ''})
        self.assertEqual(response.status_code, 302)

    def test_each_application_gets_a_distinct_default_key(self):
        with patch('ponto_apoio.init_database'), patch.dict('os.environ', {}, clear=True):
            first = create_app()
            second = create_app()
        self.assertNotEqual(first.secret_key, second.secret_key)


if __name__ == '__main__':
    unittest.main()
