import sqlite3
import unittest
from datetime import date

from ponto_apoio.database import SCHEMA
from ponto_apoio.services.campaigns import create_campaign, set_campaign_status, archive_campaign, list_campaigns, campaign_by_id
from ponto_apoio.services.students import add_student, import_students, clean_phone, duplicate_student, list_active_students, list_students, archive_student
from ponto_apoio.services.weekly_goals import add_contact, remove_contact, week_summary, change_count, ensure_week


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

    def test_search_finds_active_names_without_accents_or_case(self):
        add_student(self.db, 'João da Silva')
        add_student(self.db, 'Joana Souza')
        add_student(self.db, 'João Arquivado')
        archived = self.db.execute("SELECT id FROM students WHERE full_name='João Arquivado'").fetchone()[0]
        archive_student(self.db, archived, '2026-11-25')
        self.assertEqual([s['full_name'] for s in list_active_students(self.db, ' SILVA joao ')], ['João da Silva'])
        self.assertEqual(len(list_active_students(self.db, '')), 2)
        self.assertEqual(list_active_students(self.db, 'inexistente'), [])
        self.assertEqual([s['full_name'] for s in list_students(self.db, 'joao', archived=True)], ['João Arquivado'])

    def test_campaign_filters_and_archived_lookup(self):
        first = create_campaign(self.db, 'Matrícula de João', 'Olá')
        second = create_campaign(self.db, 'Convite semanal', 'Olá')
        third = create_campaign(self.db, 'Matrícula antiga', 'Olá')
        set_campaign_status(self.db, second, 'closed')
        archive_campaign(self.db, third, '2026-11-25')
        self.assertEqual([c['id'] for c in list_campaigns(self.db, search='JOAO matricula')], [first])
        self.assertEqual([c['id'] for c in list_campaigns(self.db, status='closed')], [second])
        self.assertEqual([c['id'] for c in list_campaigns(self.db, archived=True)], [third])
        self.assertIsNone(campaign_by_id(self.db, third))
        self.assertEqual(campaign_by_id(self.db, third, include_archived=True)['id'], third)

    def test_duplicate_names_ignore_case_and_extra_spaces(self):
        add_student(self.db, 'Ana Silva')
        student = duplicate_student(self.db, '  ANA   silva ')
        self.assertIsNotNone(student)
        self.assertIsNone(duplicate_student(self.db, 'Ana Silva', student['id']))

    def test_weekly_contacts_allow_followups_and_preserve_old_counts(self):
        week = date(2026, 11, 23)
        ensure_week(self.db, week)
        change_count(self.db, week, 0, 1)
        add_student(self.db, 'João Silva')
        student_id = self.db.execute('SELECT id FROM students').fetchone()[0]
        self.assertTrue(add_contact(self.db, week, 0, student_id))
        self.assertFalse(add_contact(self.db, week, 0, student_id))
        self.assertTrue(add_contact(self.db, week, 2, student_id))
        goals = week_summary(self.db, week)
        self.assertEqual((goals[0]['completed'], goals[0]['legacy']), (2, 1))
        self.assertEqual(goals[2]['completed'], 1)
        contact_id = goals[0]['contacts'][0]['id']
        self.assertFalse(remove_contact(self.db, date(2026, 11, 16), contact_id))
        self.assertTrue(remove_contact(self.db, week, contact_id))
        self.assertEqual(week_summary(self.db, week)[0]['completed'], 1)

    def test_contacts_cannot_exceed_daily_target(self):
        week = date(2026, 11, 23)
        ensure_week(self.db, week)
        for name in ('Ana', 'Bruno', 'Clara', 'Daniel'):
            add_student(self.db, name)
            student_id = self.db.execute('SELECT id FROM students WHERE full_name=?', (name,)).fetchone()[0]
            self.assertEqual(add_contact(self.db, week, 2, student_id), name != 'Daniel')
        goal = week_summary(self.db, week)[2]
        self.assertEqual((goal['completed'], goal['target']), (3, 3))


if __name__ == '__main__':
    unittest.main()
