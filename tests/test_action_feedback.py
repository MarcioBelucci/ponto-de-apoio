import sqlite3
import unittest
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA
from ponto_apoio.services.students import add_student
from ponto_apoio.services.campaigns import create_campaign, archive_campaign


class ActionFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        add_student(self.db, 'Sem Telefone')
        add_student(self.db, 'Com Telefone', phone='5511999999999')
        self.campaign = create_campaign(self.db, 'Teste', 'Olá')
        self.db.commit()
        with patch('ponto_apoio.init_database'):
            self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'token'
        self.patches = [patch('ponto_apoio.routes.students.get_db', return_value=self.db),
                        patch('ponto_apoio.routes.campaigns.get_db', return_value=self.db)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.db.close()

    def post(self, url, **data):
        return self.client.post(url, data={'_csrf_token': 'token', **data}, follow_redirects=True)

    def test_whatsapp_web_only_for_student_with_phone(self):
        response = self.client.get(f'/campaigns/{self.campaign}')
        self.assertEqual(response.data.count(b'Abrir no Web'), 1)
        self.assertIn(b'phone=5511999999999', response.data)

    def test_nonexistent_student_and_campaign_report_error(self):
        for response in (
            self.post('/students/999/edit', full_name='Teste'),
            self.post('/students/999/archive'),
            self.post('/campaigns/999/status', status='closed'),
            self.post('/campaigns/999/archive'),
            self.post(f'/campaigns/{self.campaign}/students/999/status', status='sent'),
        ):
            self.assertIn(b'flash error', response.data)
            self.assertNotIn(b'flash success', response.data)

    def test_archived_campaign_cannot_be_changed(self):
        student = self.db.execute("SELECT id FROM students WHERE full_name='Sem Telefone'").fetchone()[0]
        archive_campaign(self.db, self.campaign, '2026-11-27')
        self.db.commit()
        response = self.post(f'/campaigns/{self.campaign}/students/{student}/status', status='sent')
        self.assertIn(b'flash error', response.data)
        self.assertEqual(self.db.execute('SELECT status FROM sends WHERE campaign_id=? AND student_id=?', (self.campaign, student)).fetchone()[0], 'pending')


if __name__ == '__main__':
    unittest.main()
