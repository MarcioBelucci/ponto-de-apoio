import io
import sqlite3
import unittest
from unittest.mock import patch
from openpyxl import Workbook

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

    def test_optional_contacts_and_invalid_rows(self):
        content = ('Nome,Telefone,Email\n'
                   'Ana Silva,+55 (11) 99999-9999,ana@example.org\n'
                   'Bruno Souza,,\n'
                   'Carla Lima,abc,carla@example.org\n'
                   'Daniel Silva,5511999999999,email-invalido\n').encode()
        self.assertEqual(self.upload(content).status_code, 200)
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0', 'phone_column': '1', 'email_column': '2'}, follow_redirects=True)
        self.assertIn('Linha 4: telefone inválido'.encode(), response.data)
        self.assertIn('Linha 5: e-mail inválido'.encode(), response.data)
        rows = self.db.execute('SELECT full_name, phone, email FROM students ORDER BY full_name').fetchall()
        self.assertEqual([tuple(row) for row in rows], [('Ana Silva', '5511999999999', 'ana@example.org'), ('Bruno Souza', '', '')])

    def test_existing_student_is_not_overwritten(self):
        self.db.execute("INSERT INTO students (full_name, first_name, phone, email) VALUES ('Ana Silva', 'Ana', '5511888888888', 'antigo@example.org')")
        self.db.commit()
        self.upload(b'Nome,Telefone,Email\nAna Silva,5511999999999,novo@example.org\n')
        self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0', 'phone_column': '1', 'email_column': '2'})
        self.assertEqual(tuple(self.db.execute('SELECT phone, email FROM students').fetchone()), ('5511888888888', 'antigo@example.org'))

    def test_xlsx_and_column_validation(self):
        book = Workbook()
        sheet = book.active
        sheet.append(['Nome', 'Telefone', 'Email'])
        sheet.append(['Joana Silva', 5511999999999, 'joana@example.org'])
        file = io.BytesIO()
        book.save(file)
        self.assertEqual(self.upload(file.getvalue(), 'alunos.xlsx').status_code, 200)
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0', 'phone_column': '0', 'email_column': '2'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 0)
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0', 'phone_column': '1', 'email_column': '2'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(tuple(self.db.execute('SELECT phone, email FROM students').fetchone()), ('5511999999999', 'joana@example.org'))

    def test_phone_decimal_zero_is_removed_without_changing_digits(self):
        self.upload(b'Nome,Telefone\nAna Silva,5519991604470.0\nBruno Souza,19991604470.0\nCarla Lima,5511999999999.5\n')
        response = self.client.post('/import/confirm', data={'_csrf_token': 'token', 'name_column': '0', 'phone_column': '1'}, follow_redirects=True)
        rows = self.db.execute('SELECT full_name, phone FROM students ORDER BY full_name').fetchall()
        self.assertEqual([tuple(row) for row in rows], [('Ana Silva', '5519991604470'), ('Bruno Souza', '19991604470')])
        self.assertIn('Linha 4: telefone inválido'.encode(), response.data)


if __name__ == '__main__':
    unittest.main()
