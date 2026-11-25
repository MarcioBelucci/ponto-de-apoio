import sqlite3
import unittest
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA


class BackupTests(unittest.TestCase):
    def test_download_is_consistent_and_omits_pending_imports(self):
        source = sqlite3.connect(':memory:')
        source.executescript(SCHEMA)
        source.execute("INSERT INTO students (full_name, first_name) VALUES ('Ana Silva', 'Ana')")
        source.execute("INSERT INTO pending_imports (token, rows_json) VALUES ('secret', '[]')")
        source.commit()
        try:
            with patch('ponto_apoio.init_database'):
                app = create_app()
            app.config['TESTING'] = True
            client = app.test_client()
            with client.session_transaction() as session:
                session['_csrf_token'] = 'token'
            with patch('ponto_apoio.routes.backup.get_db', return_value=source):
                response = client.post('/backup/download', data={'_csrf_token': 'token'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response.headers['Content-Disposition'])
            copy = sqlite3.connect(':memory:')
            try:
                copy.deserialize(response.data)
                self.assertEqual(copy.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(copy.execute('SELECT full_name FROM students').fetchone()[0], 'Ana Silva')
                self.assertEqual(copy.execute('SELECT COUNT(*) FROM pending_imports').fetchone()[0], 0)
                self.assertEqual(source.execute('SELECT COUNT(*) FROM pending_imports').fetchone()[0], 1)
            finally:
                copy.close()
        finally:
            source.close()


if __name__ == '__main__':
    unittest.main()
