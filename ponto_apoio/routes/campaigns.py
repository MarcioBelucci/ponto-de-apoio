"""Rotas de criação, acompanhamento e envio de outreaches."""

from datetime import datetime
from urllib.parse import quote

from flask import flash, redirect, render_template, request, url_for

from ponto_apoio.database import get_db
from ponto_apoio.services.campaigns import (
    archive_campaign,
    campaign_by_id,
    create_campaign,
    list_campaign_students,
    list_campaigns,
    set_campaign_status as update_campaign_status,
    set_send_status as update_send_status,
    sync_campaign,
)


def register_campaign_routes(app):
    """Registra as rotas de outreaches e destinatários."""

    @app.route("/campaigns")
    def campaigns():
        return render_template("campaigns.html", campaigns=list_campaigns(get_db()))

    @app.route("/campaigns/new", methods=["GET", "POST"])
    def new_campaign():
        if request.method == "GET":
            return render_template("campaign_form.html")
        title = request.form.get("title", "").strip()
        message_template = request.form.get("message_template", "").strip()
        if not title or not message_template:
            flash("Informe o título e a mensagem do outreach.", "error")
            return render_template("campaign_form.html", title=title, message_template=message_template)
        db = get_db()
        campaign_id = create_campaign(db, title, message_template)
        db.commit()
        flash("Outreach criado.", "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    @app.route("/campaigns/<int:campaign_id>")
    def campaign_detail(campaign_id):
        db = get_db()
        campaign = campaign_by_id(db, campaign_id)
        if not campaign:
            flash("Outreach não encontrado.", "error")
            return redirect(url_for("campaigns"))
        return render_template(
            "campaign_detail.html",
            campaign=campaign,
            students=list_campaign_students(db, campaign_id),
            quote=quote,
        )

    @app.post("/campaigns/<int:campaign_id>/students/<int:student_id>/status")
    def set_send_status(campaign_id, student_id):
        status = request.form.get("status")
        if status not in {"pending", "opened", "sent", "skip"}:
            flash("Situação inválida.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))
        db = get_db()
        update_send_status(db, campaign_id, student_id, status, datetime.now().isoformat(timespec="seconds"))
        db.commit()
        flash("Situação atualizada.", "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    @app.post("/campaigns/<int:campaign_id>/sync", endpoint="sync_campaign")
    def sync_campaign_route(campaign_id):
        db = get_db()
        campaign = campaign_by_id(db, campaign_id)
        if not campaign:
            flash("Outreach não encontrado.", "error")
            return redirect(url_for("campaigns"))
        if campaign["status"] != "open":
            flash("Apenas outreaches em andamento podem receber alunos novos.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))
        added = sync_campaign(db, campaign_id)
        db.commit()
        flash(f"Sincronização concluída: {added} aluno(s) novo(s) incluído(s).", "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    @app.post("/campaigns/<int:campaign_id>/status")
    def set_campaign_status(campaign_id):
        status = request.form.get("status")
        if status not in {"open", "closed"}:
            flash("Situação inválida.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))
        db = get_db()
        update_campaign_status(db, campaign_id, status)
        db.commit()
        message = "Outreach reaberto. Alunos novos voltarão a ser incluídos automaticamente." if status == "open" else "Outreach encerrado. O histórico foi preservado e novos alunos não serão incluídos."
        flash(message, "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    @app.post("/campaigns/<int:campaign_id>/archive", endpoint="archive_campaign")
    def archive_campaign_route(campaign_id):
        db = get_db()
        archive_campaign(db, campaign_id, datetime.now().isoformat(timespec="seconds"))
        db.commit()
        flash("Outreach arquivado. O histórico foi preservado.", "success")
        return redirect(url_for("campaigns"))
