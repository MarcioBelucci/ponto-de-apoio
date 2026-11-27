import json
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA
from ponto_apoio.services.students import add_student, archive_student, import_students
from ponto_apoio.services.campaigns import create_campaign
from ponto_apoio.services.weekly_goals import ensure_week, add_contact


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SCHEMA)
        add_student(self.db, 'Ana Silva', phone='111')
        self.source = self.db.execute('SELECT id FROM students').fetchone()[0]
        self.campaign = create_campaign(self.db, 'Teste', 'Olá')
        week = date(2026, 11, 23)
        ensure_week(self.db, week)
        add_contact(self.db, week, 0, self.source)
        self.db.execute("UPDATE sends SET status='sent', sent_at='2026-11-23T10:00:00' WHERE student_id=?", (self.source,))
        archive_student(self.db, self.source, '2026-11-24')
        add_student(self.db, 'Ana Silva', phone='222')
        self.target = self.db.execute('SELECT MAX(id) FROM students').fetchone()[0]
        add_contact(self.db, week, 0, self.target)
        self.db.commit()
        with patch('ponto_apoio.init_database'):
            app = create_app()
        app.config['TESTING'] = True
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'token'
        self.db_patch = patch('ponto_apoio.routes.students.get_db', return_value=self.db)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.db.close()

    def test_merge_requires_confirmation_and_preserves_sent_and_audit(self):
        url = f'/students/{self.source}/merge'
        self.assertIn(b'222', self.client.get(url).data)
        self.client.post(url, data={'_csrf_token': 'token', 'target_id': self.target})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM student_merges').fetchone()[0], 0)
        response = self.client.post(url, data={'_csrf_token': 'token', 'target_id': self.target, 'confirm': 'yes'})
        self.assertEqual(response.status_code, 302)
        rows = self.db.execute('SELECT student_id, status, sent_at FROM sends WHERE campaign_id=?', (self.campaign,)).fetchall()
        self.assertEqual([tuple(row) for row in rows], [(self.target, 'sent', '2026-11-23T10:00:00')])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM weekly_contacts').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT merged_into FROM students WHERE id=?', (self.source,)).fetchone()[0], self.target)
        snapshot = json.loads(self.db.execute('SELECT snapshot FROM student_merges').fetchone()[0])
        self.assertEqual(snapshot['source']['phone'], '111')
        self.assertEqual(snapshot['target']['phone'], '222')
        self.assertEqual(len(snapshot['source_contacts']), 1)
        self.assertEqual(len(snapshot['target_contacts']), 1)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_archived_name_import_is_flagged_and_no_duplicate_created(self):
        errors = []
        result = import_students(self.db, [['ana silva']], 0, errors=errors)
        self.assertEqual(result, (0, 1))
        self.assertIn('arquivados', errors[0])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 2)

    def test_older_database_gets_migration(self):
        from ponto_apoio.database import init_db
        old_db = sqlite3.connect(':memory:')
        try:
            old_db.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, full_name TEXT, first_name TEXT, active INTEGER, archived_at TEXT)")
            with patch('ponto_apoio.database.get_db', return_value=old_db):
                init_db()
            self.assertIn('merged_into', [row[1] for row in old_db.execute('PRAGMA table_info(students)')])
            self.assertEqual(old_db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='student_merges'").fetchone()[0], 1)
        finally:
            old_db.close()


if __name__ == '__main__':
    unittest.main()
