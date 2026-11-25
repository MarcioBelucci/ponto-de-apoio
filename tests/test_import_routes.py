import io
import sqlite3
import unittest
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.patch_db = patch('ponto_apoio.routes.students.get_db', return_value=self.db)
        self.patch_db.start()
        with patch('ponto_apoio.init_database'):
            self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'token'

    def tearDown(self):
        self.patch_db.stop()
        self.db.close()

    def upload(self, content=b'Nome\nAna Silva\nBruno Souza\n', filename='alunos.csv'):
        return self.client.post('/import', data={'_csrf_token': 'token', 'file': (io.BytesIO(content), filename)})

    def test_import_uses_server_copy_and_cannot_repeat(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'name="rows"', response.data)
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0', 'rows': '[]'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM pending_imports').fetchone()[0], 0)
        self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0'})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 2)

    def test_cancel_and_invalid_column(self):
        self.upload()
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '99'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 0)
        self.client.get('/import')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM pending_imports').fetchone()[0], 0)

    def test_expired_and_invalid_file(self):
        self.upload()
        self.db.execute("UPDATE pending_imports SET created_at=datetime('now', '-2 days')")
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 0)
        self.assertEqual(self.upload(b'not an excel file', 'alunos.xlsx').status_code, 302)


if __name__ == '__main__':
    unittest.main()
