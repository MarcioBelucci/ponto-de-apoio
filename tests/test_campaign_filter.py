import sqlite3
import unittest
from unittest.mock import patch

from ponto_apoio import create_app
from ponto_apoio.database import SCHEMA
from ponto_apoio.services.students import add_student
from ponto_apoio.services.campaigns import create_campaign


class CampaignFilterTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        for number in range(25):
            add_student(self.db, f'Aluno {number:02}')
        add_student(self.db, 'João Silva')
        self.campaign = create_campaign(self.db, 'Campanha', 'Olá, {nome}')
        self.db.commit()
        with patch('ponto_apoio.init_database'):
            self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'token'
        self.db_patch = patch('ponto_apoio.routes.campaigns.get_db', return_value=self.db)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.db.close()

    def test_pagination_search_and_filter_preserved_after_status_change(self):
        url = f'/campaigns/{self.campaign}'
        first = self.client.get(url)
        self.assertIn('Página 1 de 2'.encode(), first.data)
        self.assertIn(b'Aluno 19', first.data)
        self.assertNotIn(b'Aluno 20', first.data)
        second = self.client.get(url + '?page=2')
        self.assertIn(b'Aluno 20', second.data)
        filtered = self.client.get(url + '?q=joao&status=pending')
        self.assertIn('João Silva'.encode(), filtered.data)
        self.assertIn(b'0 de 26 enviados', filtered.data)
        student = self.db.execute("SELECT id FROM students WHERE full_name='João Silva'").fetchone()[0]
        response = self.client.post(f'{url}/students/{student}/status?q=joao&filter_status=pending&page=1',
                                    data={'_csrf_token': 'token', 'status': 'sent'}, follow_redirects=True)
        self.assertIn(b'1 de 26 enviados', response.data)
        self.assertIn('Nenhum destinatário encontrado'.encode(), response.data)
        self.assertNotIn('João Silva'.encode(), response.data)

    def test_page_is_clamped_and_status_filter_works(self):
        url = f'/campaigns/{self.campaign}'
        response = self.client.get(url + '?page=999')
        self.assertIn('Página 2 de 2'.encode(), response.data)
        response = self.client.get(url + '?status=sent')
        self.assertIn('Nenhum destinatário encontrado'.encode(), response.data)


if __name__ == '__main__':
    unittest.main()
