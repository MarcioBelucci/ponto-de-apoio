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
    restore_campaign,
    set_campaign_status as update_campaign_status,
    set_send_status as update_send_status,
    sync_campaign,
)


def register_campaign_routes(app):
    """Registra as rotas de outreaches e destinatários."""

    @app.route("/campaigns")
    def campaigns():
        search = request.args.get('q', '').strip()
        status = request.args.get('status', 'all')
        if status not in {'all', 'open', 'closed'}:
            status = 'all'
        archived = request.args.get('view') == 'archived'
        return render_template("campaigns.html", campaigns=list_campaigns(get_db(), status=status, archived=archived, search=search), search=search, status=status, archived=archived)

    @app.get('/campaigns/<int:campaign_id>/archive-view')
    def archived_campaign_detail(campaign_id):
        db = get_db()
        campaign = campaign_by_id(db, campaign_id, include_archived=True)
        if not campaign or not campaign['archived_at']:
            flash('Outreach arquivado não encontrado.', 'error')
            return redirect(url_for('campaigns', view='archived'))
        return render_template('archived_campaign.html', campaign=campaign, students=list_campaign_students(db, campaign_id))

    @app.post('/campaigns/<int:campaign_id>/restore')
    def restore_campaign_route(campaign_id):
        db = get_db()
        restored = restore_campaign(db, campaign_id)
        db.commit()
        if not restored:
            flash('Outreach arquivado não encontrado.', 'error')
            return redirect(url_for('campaigns', view='archived'))
        flash('Outreach recuperado como encerrado. O histórico foi preservado; você pode reabri-lo quando quiser.', 'success')
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))

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
        from ponto_apoio.services.students import normalize_search
        search = request.args.get("q", "").strip()
        status = request.args.get("status", "all")
        if status not in {"all", "pending", "opened", "sent", "skip"}:
            status = "all"
        all_students = list_campaign_students(db, campaign_id)
        terms = normalize_search(search).split()
        filtered = [s for s in all_students if (status == "all" or s["status"] == status)
                    and all(term in normalize_search(s["full_name"]) for term in terms)]
        pages = max(1, (len(filtered) + 19) // 20)
        page = max(1, min(request.args.get("page", 1, type=int) or 1, pages))
        return render_template(
            "campaign_detail.html",
            campaign=campaign,
            students=filtered[(page - 1) * 20:page * 20],
            search=search, status=status, page=page, pages=pages,
            total=len(all_students), filtered_total=len(filtered),
            sent_total=sum(s["status"] == "sent" for s in all_students),
            quote=quote,
        )

    @app.post("/campaigns/<int:campaign_id>/students/<int:student_id>/status")
    def set_send_status(campaign_id, student_id):
        search = request.args.get("q", "")
        selected_status = request.args.get("filter_status", "all")
        page = request.args.get("page", 1, type=int) or 1
        destination = url_for("campaign_detail", campaign_id=campaign_id, q=search,
                              status=selected_status, page=page)
        status = request.form.get("status")
        if status not in {"pending", "opened", "sent", "skip"}:
            flash("Situação inválida.", "error")
            return redirect(destination)
        db = get_db()
        changed = update_send_status(db, campaign_id, student_id, status, datetime.now().isoformat(timespec="seconds"))
        db.commit()
        if not changed:
            flash("Destinatário ou outreach não encontrado, ou outreach arquivado.", "error")
            if not campaign_by_id(db, campaign_id):
                return redirect(url_for("campaigns"))
            return redirect(destination)
        flash("Situação atualizada.", "success")
        return redirect(destination)

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
        changed = update_campaign_status(db, campaign_id, status)
        db.commit()
        if not changed:
            flash("Outreach não encontrado ou arquivado.", "error")
            return redirect(url_for("campaigns"))
        message = "Outreach reaberto. Alunos novos voltarão a ser incluídos automaticamente." if status == "open" else "Outreach encerrado. O histórico foi preservado e novos alunos não serão incluídos."
        flash(message, "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    @app.post("/campaigns/<int:campaign_id>/archive", endpoint="archive_campaign")
    def archive_campaign_route(campaign_id):
        db = get_db()
        changed = archive_campaign(db, campaign_id, datetime.now().isoformat(timespec="seconds"))
        db.commit()
        flash("Outreach arquivado. O histórico foi preservado." if changed else "Outreach não encontrado ou já arquivado.", "success" if changed else "error")
        return redirect(url_for("campaigns"))
