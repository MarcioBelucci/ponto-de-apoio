"""Rotas do painel inicial."""

from datetime import date, timedelta

from flask import flash, redirect, render_template, request, url_for

from ponto_apoio.database import get_db
from ponto_apoio.services.campaigns import list_campaigns
from ponto_apoio.services.students import list_active_students
from ponto_apoio.services.weekly_goals import add_contact, remove_contact, ensure_week, monday, set_targets, week_summary


def register_dashboard_routes(app):
    """Registra a página inicial e seus indicadores."""

    @app.route("/")
    def dashboard():
        db = get_db()
        today = date.today()
        current_week = monday(today)
        ensure_week(db, current_week)
        requested = request.args.get("week")
        try:
            week = monday(date.fromisoformat(requested)) if requested else current_week
        except ValueError:
            week = current_week
        if week > current_week:
            week = current_week
        if week == current_week:
            ensure_week(db, week)
        goals = week_summary(db, week)
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
            goals=goals,
            students=list_active_students(db),
            week=week,
            current_week=current_week,
            today_index=today.weekday(),
            previous_week=week - timedelta(days=7),
            next_week=week + timedelta(days=7),
        )

    @app.post("/weekly-goals/contact")
    def add_weekly_contact():
        try:
            day = int(request.form.get("day", ""))
            student_id = int(request.form.get("student_id", ""))
            if day not in range(4) or student_id <= 0:
                raise ValueError
        except ValueError:
            flash("Não foi possível atualizar a atividade.", "error")
            return redirect(url_for("dashboard"))
        db = get_db()
        week = monday(date.today())
        ensure_week(db, week)
        changed = add_contact(db, week, day, student_id)
        db.commit()
        if not changed:
            flash("Meta já atingida, aluno inválido ou já registrado nesta atividade da semana.", "error")
        else:
            flash("Contato registrado.", "success")
        return redirect(url_for("dashboard") + "#weekly-goals")

    @app.post('/weekly-goals/contact/<int:contact_id>/remove')
    def remove_weekly_contact(contact_id):
        db = get_db()
        changed = remove_contact(db, monday(date.today()), contact_id)
        db.commit()
        flash("Registro removido." if changed else "Registro não encontrado nesta semana.", "success" if changed else "error")
        return redirect(url_for("dashboard") + "#weekly-goals")

    @app.post("/weekly-goals/targets")
    def update_weekly_targets():
        try:
            targets = [int(request.form.get(f"target_{day}", "")) for day in range(4)]
            if any(target < 0 or target > 999 for target in targets):
                raise ValueError
        except ValueError:
            flash("Informe metas entre 0 e 999.", "error")
            return redirect(url_for("dashboard") + "#weekly-goals")
        db = get_db()
        week = monday(date.today())
        ensure_week(db, week)
        set_targets(db, week, targets)
        db.commit()
        flash("Metas desta semana atualizadas.", "success")
        return redirect(url_for("dashboard") + "#weekly-goals")
