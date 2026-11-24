"""Rotas do painel inicial."""

from flask import render_template

from ponto_apoio.database import get_db
from ponto_apoio.services.campaigns import list_campaigns


def register_dashboard_routes(app):
    """Registra a página inicial e seus indicadores."""

    @app.route("/")
    def dashboard():
        db = get_db()
        total_students = db.execute(
            "SELECT COUNT(*) FROM students WHERE active = 1"
        ).fetchone()[0]
        phone_ready = db.execute(
            """
            SELECT COUNT(*) FROM students
            WHERE active = 1 AND phone IS NOT NULL AND phone != ''
            """
        ).fetchone()[0]
        return render_template(
            "dashboard.html",
            total_students=total_students,
            phone_ready=phone_ready,
            campaigns=list_campaigns(db, limit=5),
        )
