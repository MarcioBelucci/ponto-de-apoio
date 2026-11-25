import sqlite3
import unittest
from datetime import date

from ponto_apoio.database import SCHEMA
from ponto_apoio.services.campaigns import create_campaign, set_campaign_status
from ponto_apoio.services.students import add_student, import_students, clean_phone, duplicate_student
from ponto_apoio.services.weekly_goals import change_count, ensure_week


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.executescript(SCHEMA)

    def tearDown(self):
        self.db.close()

    def test_campaign_membership_respects_closed_status(self):
        add_student(self.db, 'Ana Silva')
        campaign = create_campaign(self.db, 'Teste', 'Olá, {nome}')
        add_student(self.db, 'Bruno Souza')
        set_campaign_status(self.db, campaign, 'closed')
        add_student(self.db, 'Clara Lima')
        names = [row[0] for row in self.db.execute('SELECT s.full_name FROM sends se JOIN students s ON s.id=se.student_id WHERE se.campaign_id=? ORDER BY s.full_name', (campaign,))]
        self.assertEqual(names, ['Ana Silva', 'Bruno Souza'])

    def test_import_ignores_duplicate_and_empty_names(self):
        add_student(self.db, 'Ana Silva')
        result = import_students(self.db, [['ana silva'], [' Bruno Souza '], ['']], 0)
        self.assertEqual(result, (1, 2))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 2)

    def test_weekly_count_stays_within_bounds(self):
        week = date(2026, 11, 23)
        ensure_week(self.db, week)
        self.assertFalse(change_count(self.db, week, 0, -1))
        for _ in range(5):
            self.assertTrue(change_count(self.db, week, 0, 1))
        self.assertFalse(change_count(self.db, week, 0, 1))
        self.assertTrue(change_count(self.db, week, 0, -1))

    def test_phone_validation(self):
        self.assertEqual(clean_phone(''), '')
        self.assertEqual(clean_phone('+55 (11) 99999-9999'), '5511999999999')
        for value in ('abc', '123', '00123456789', '5511999999999 ramal 12'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                clean_phone(value)

    def test_duplicate_names_ignore_case_and_extra_spaces(self):
        add_student(self.db, 'Ana Silva')
        student = duplicate_student(self.db, '  ANA   silva ')
        self.assertIsNotNone(student)
        self.assertIsNone(duplicate_student(self.db, 'Ana Silva', student['id']))


if __name__ == '__main__':
    unittest.main()
