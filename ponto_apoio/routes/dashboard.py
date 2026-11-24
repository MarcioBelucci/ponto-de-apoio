"""Rotas do painel inicial."""

from datetime import date, timedelta

from flask import flash, redirect, render_template, request, url_for

from ponto_apoio.database import get_db
from ponto_apoio.services.campaigns import list_campaigns
from ponto_apoio.services.weekly_goals import change_count, ensure_week, monday, set_targets, week_summary


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
            week=week,
            current_week=current_week,
            today_index=today.weekday(),
            previous_week=week - timedelta(days=7),
            next_week=week + timedelta(days=7),
        )

    @app.post("/weekly-goals/count")
    def update_weekly_count():
        try:
            day = int(request.form.get("day", ""))
            delta = int(request.form.get("delta", ""))
            if day not in range(4) or delta not in (-1, 1):
                raise ValueError
        except ValueError:
            flash("Não foi possível atualizar a atividade.", "error")
            return redirect(url_for("dashboard"))
        db = get_db()
        week = monday(date.today())
        ensure_week(db, week)
        changed = change_count(db, week, day, delta)
        db.commit()
        if not changed:
            flash("A meta já foi atingida ou não há registro para desfazer.", "error")
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
