"""Rotas de alunos e importação de planilhas."""

import json
import secrets
from datetime import datetime

from flask import flash, redirect, render_template, request, session, url_for
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile

from ponto_apoio.database import get_db
from ponto_apoio.services.students import (
    add_student,
    archive_student,
    clean_phone,
    duplicate_student,
    import_students,
    list_active_students,
    read_sheet,
    update_student,
)


def register_student_routes(app):
    """Registra as rotas de gerenciamento de alunos."""

    @app.route("/students")
    def students():
        search = request.args.get("q", "").strip()
        return render_template("students.html", students=list_active_students(get_db(), search), search=search)

    @app.post("/students", endpoint="add_student")
    def add_student_route():
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Informe o nome completo do aluno.", "error")
            return redirect(url_for("students"))

        db = get_db()
        try:
            clean_phone(request.form.get("phone", ""))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("students"))
        duplicate = duplicate_student(db, full_name)
        linked = add_student(
            db,
            full_name,
            request.form.get("phone", ""),
            request.form.get("email", ""),
            request.form.get("program", "BIU MLP"),
            request.form.get("notes", ""),
        )
        db.commit()
        if duplicate:
            flash("Aviso: já existe outro aluno ativo com esse nome. Confira se os cadastros correspondem a pessoas diferentes.", "error")
        suffix = f" Incluído em {linked} outreach(es) em andamento." if linked else ""
        flash(f"Aluno adicionado.{suffix}", "success")
        return redirect(url_for("students"))

    @app.post("/students/<int:student_id>/edit")
    def edit_student(student_id):
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("O nome não pode ficar vazio.", "error")
            return redirect(url_for("students"))

        db = get_db()
        try:
            clean_phone(request.form.get("phone", ""))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("students"))
        duplicate = duplicate_student(db, full_name, student_id)
        update_student(
            db, student_id, full_name, request.form.get("phone", ""),
            request.form.get("email", ""), request.form.get("program", "BIU MLP"),
            request.form.get("notes", ""),
        )
        db.commit()
        if duplicate:
            flash("Aviso: já existe outro aluno ativo com esse nome. Confira se os cadastros correspondem a pessoas diferentes.", "error")
        flash("Dados do aluno atualizados.", "success")
        return redirect(url_for("students"))

    @app.post("/students/<int:student_id>/archive", endpoint="archive_student")
    def archive_student_route(student_id):
        db = get_db()
        archive_student(db, student_id, datetime.now().isoformat(timespec="seconds"))
        db.commit()
        flash("Aluno arquivado. O histórico foi preservado.", "success")
        return redirect(url_for("students"))

    @app.route("/import", methods=["GET", "POST"], endpoint="import_students")
    def import_students_route():
        if request.method == "GET":
            token = session.pop("pending_import", None)
            if token:
                db = get_db()
                db.execute("DELETE FROM pending_imports WHERE token=?", (token,))
                db.commit()
            return render_template("import.html", preview=None)
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Escolha uma planilha para importar.", "error")
            return redirect(url_for("import_students"))
        try:
            rows = read_sheet(upload)
        except (ValueError, UnicodeDecodeError, InvalidFileException, BadZipFile, OSError, KeyError):
            flash("Não foi possível ler a planilha. Verifique o arquivo CSV ou XLSX.", "error")
            return redirect(url_for("import_students"))
        if not rows or not rows[0]:
            flash("A planilha está vazia.", "error")
            return redirect(url_for("import_students"))

        headers = [str(value or f"Coluna {index + 1}").strip() for index, value in enumerate(rows[0])]
        preview = [["" if value is None else str(value) for value in row] for row in rows[1:51]]
        data = [["" if value is None else str(value) for value in row] for row in rows]
        token = secrets.token_urlsafe(32)
        db = get_db()
        db.execute("DELETE FROM pending_imports WHERE created_at < datetime('now', '-1 day')")
        previous = session.get("pending_import")
        if previous:
            db.execute("DELETE FROM pending_imports WHERE token=?", (previous,))
        db.execute("INSERT INTO pending_imports (token, rows_json) VALUES (?, ?)", (token, json.dumps(data)))
        db.commit()
        session["pending_import"] = token
        return render_template("import.html", preview=preview, headers=headers)

    @app.post("/import/confirm")
    def confirm_import():
        token = session.get("pending_import")
        db = get_db()
        pending = db.execute("SELECT rows_json FROM pending_imports WHERE token=? AND created_at >= datetime('now', '-1 day')", (token,)).fetchone() if token else None
        if not pending:
            session.pop("pending_import", None)
            flash("A importação expirou ou já foi concluída. Envie a planilha novamente.", "error")
            return redirect(url_for("import_students"))
        rows = json.loads(pending["rows_json"])
        try:
            name_index = int(request.form.get("name_column", "-1"))
        except ValueError:
            name_index = -1
        if not 0 <= name_index < len(rows[0]):
            flash("Escolha a coluna que contém os nomes.", "error")
            headers = [str(value or f"Coluna {index + 1}") for index, value in enumerate(rows[0])]
            return render_template("import.html", preview=rows[1:51], headers=headers), 400
        added, skipped = import_students(db, rows[1:], name_index)
        db.execute("DELETE FROM pending_imports WHERE token=?", (token,))
        db.commit()
        session.pop("pending_import", None)
        flash(f"Importação concluída: {added} aluno(s) adicionado(s); {skipped} linha(s) ignorada(s).", "success")
        return redirect(url_for("students"))
