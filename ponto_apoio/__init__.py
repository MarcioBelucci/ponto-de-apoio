"""Configuração da aplicação Ponto de Apoio."""

import os
import secrets
import hmac

from flask import Flask, abort, request, session

from ponto_apoio.database import init_app as init_database
from ponto_apoio.routes.campaigns import register_campaign_routes
from ponto_apoio.routes.dashboard import register_dashboard_routes
from ponto_apoio.routes.students import register_student_routes


def create_app():
    """Cria e configura a aplicação Flask."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("OUTREACHES_SECRET") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    @app.before_request
    def verify_csrf():
        if request.method == "POST":
            expected = session.get("_csrf_token", "")
            supplied = request.form.get("_csrf_token", "")
            if not expected or not hmac.compare_digest(expected, supplied):
                abort(400, "Formulário expirado ou inválido. Atualize a página e tente novamente.")

    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    init_database(app)
    register_dashboard_routes(app)
    register_student_routes(app)
    register_campaign_routes(app)
    return app
