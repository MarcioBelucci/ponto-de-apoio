"""Rotas de alunos e importação de planilhas."""

import json
from datetime import datetime

from flask import flash, redirect, render_template, request, url_for

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
        return render_template("students.html", students=list_active_students(get_db()))

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
            return render_template("import.html", preview=None)
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Escolha uma planilha para importar.", "error")
            return redirect(url_for("import_students"))
        try:
            rows = read_sheet(upload)
        except (ValueError, UnicodeDecodeError) as error:
            flash(str(error), "error")
            return redirect(url_for("import_students"))
        if not rows or not rows[0]:
            flash("A planilha está vazia.", "error")
            return redirect(url_for("import_students"))

        headers = [str(value or f"Coluna {index + 1}").strip() for index, value in enumerate(rows[0])]
        preview = [["" if value is None else str(value) for value in row] for row in rows[1:51]]
        return render_template("import.html", preview=preview, headers=headers, rows=rows[1:])

    @app.post("/import/confirm")
    def confirm_import():
        rows = json.loads(request.form.get("rows", "[]"))
        name_index = int(request.form.get("name_column", "-1"))
        if name_index < 0:
            flash("Escolha a coluna que contém os nomes.", "error")
            return redirect(url_for("import_students"))
        db = get_db()
        added, skipped = import_students(db, rows, name_index)
        db.commit()
        flash(f"Importação concluída: {added} aluno(s) adicionado(s); {skipped} linha(s) ignorada(s).", "success")
        return redirect(url_for("students"))
