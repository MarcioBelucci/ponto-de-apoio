"""Configuração da aplicação Ponto de Apoio."""

import os

from flask import Flask

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
        SECRET_KEY=os.environ.get(
            "OUTREACHES_SECRET", "troque-esta-chave-antes-de-compartilhar"
        ),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )

    init_database(app)
    register_dashboard_routes(app)
    register_student_routes(app)
    register_campaign_routes(app)
    return app
