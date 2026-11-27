import sqlite3
import unittest
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA
from ponto_apoio.services.students import add_student
from ponto_apoio.services.campaigns import create_campaign


class ListPaginationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        for number in range(25):
            add_student(self.db, f'Aluno {number:02}')
            campaign = create_campaign(self.db, f'Semana {number:02}', 'Olá')
            self.db.execute("UPDATE campaigns SET status='closed', archived_at='2026-11-27' WHERE id=?", (campaign,))
        self.db.execute("UPDATE students SET active=0, archived_at='2026-11-27'")
        self.db.commit()
        with patch('ponto_apoio.init_database'):
            app = create_app()
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.patches = [patch('ponto_apoio.routes.students.get_db', return_value=self.db),
                        patch('ponto_apoio.routes.campaigns.get_db', return_value=self.db)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.db.close()

    def test_archived_students_search_and_pages(self):
        response = self.client.get('/students?view=archived&q=aluno')
        self.assertIn('Exibindo 20 de 25'.encode(), response.data)
        self.assertIn(b'Aluno 19', response.data)
        self.assertNotIn(b'Aluno 20', response.data)
        self.assertIn(b'view=archived', response.data)
        self.assertIn(b'q=aluno', response.data)
        response = self.client.get('/students?view=archived&q=aluno&page=999')
        self.assertIn(b'Aluno 20', response.data)
        self.assertIn('Página 2 de 2'.encode(), response.data)
        self.assertNotIn(b'Aluno 00', response.data)
        self.assertIn('Nenhum aluno encontrado'.encode(), self.client.get('/students?view=archived&q=xyz').data)

    def test_archived_campaigns_filters_and_pages(self):
        response = self.client.get('/campaigns?view=archived&status=closed&q=semana')
        self.assertIn(b'Exibindo 20 de 25', response.data)
        self.assertIn(b'view=archived', response.data)
        self.assertIn(b'status=closed', response.data)
        self.assertIn(b'q=semana', response.data)
        response = self.client.get('/campaigns?view=archived&status=closed&q=semana&page=2')
        self.assertIn(b'Exibindo 5 de 25', response.data)
        self.assertIn('Página 2 de 2'.encode(), response.data)
        self.assertIn(b'Nenhum outreach encontrado', self.client.get('/campaigns?view=archived&status=open').data)


if __name__ == '__main__':
    unittest.main()
