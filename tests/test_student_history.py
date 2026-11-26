import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA
from ponto_apoio.services.students import add_student, archive_student
from ponto_apoio.services.campaigns import create_campaign, archive_campaign
from ponto_apoio.services.weekly_goals import ensure_week, add_contact


class StudentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        add_student(self.db, 'João Silva')
        self.student = self.db.execute('SELECT id FROM students').fetchone()[0]
        with patch('ponto_apoio.init_database'):
            self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.db_patch = patch('ponto_apoio.routes.students.get_db', return_value=self.db)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.db.close()

    def test_history_includes_archived_records_and_excludes_other_students(self):
        campaign = create_campaign(self.db, 'Outreach antigo', 'Olá')
        self.db.execute("UPDATE sends SET status='sent', sent_at='2026-11-25T10:00:00' WHERE campaign_id=? AND student_id=?", (campaign, self.student))
        archive_campaign(self.db, campaign, '2026-11-26')
        week = date(2026, 11, 23)
        ensure_week(self.db, week)
        add_contact(self.db, week, 2, self.student)
        archive_student(self.db, self.student, '2026-11-26')
        add_student(self.db, 'Outra Pessoa')
        other = self.db.execute("SELECT id FROM students WHERE full_name='Outra Pessoa'").fetchone()[0]
        add_contact(self.db, week, 3, other)
        response = self.client.get(f'/students/{self.student}/history')
        self.assertEqual(response.status_code, 200)
        self.assertIn('João Silva'.encode(), response.data)
        self.assertIn(b'Outreach antigo', response.data)
        self.assertIn(b'Convites para reuni', response.data)
        self.assertIn(b'2026-11-25T10:00:00', response.data)
        self.assertIn(f'/campaigns/{campaign}/archive-view'.encode(), response.data)
        self.assertNotIn(b'Mensagens de parab', response.data)

    def test_empty_and_missing_student(self):
        response = self.client.get(f'/students/{self.student}/history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Nenhum contato identificado', response.data)
        self.assertEqual(self.client.get('/students/9999/history').status_code, 404)
        self.assertIn(f'/students/{self.student}/history'.encode(), self.client.get('/students').data)


if __name__ == '__main__':
    unittest.main()
