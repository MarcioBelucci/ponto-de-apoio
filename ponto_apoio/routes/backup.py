"""Download de uma cópia consistente do banco de dados."""

import io
import sqlite3
from datetime import datetime

from flask import render_template, send_file

from ponto_apoio.database import get_db


def register_backup_routes(app):
    @app.get('/backup')
    def backup_page():
        return render_template('backup.html')

    @app.post('/backup/download')
    def download_backup():
        destination = sqlite3.connect(':memory:')
        try:
            get_db().backup(destination)
            destination.execute('DELETE FROM pending_imports')
            destination.commit()
            data = destination.serialize()
        finally:
            destination.close()
        response = send_file(
            io.BytesIO(data), mimetype='application/vnd.sqlite3', as_attachment=True,
            download_name=f"ponto-de-apoio-{datetime.now():%Y-%m-%d-%H%M%S}.db",
        )
        response.headers['Cache-Control'] = 'no-store'
        return response
