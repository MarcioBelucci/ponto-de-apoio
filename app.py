import csv
import io
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, flash, g, redirect, render_template, request, url_for
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE = DATA_DIR / "outreaches.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("OUTREACHES_SECRET", "troque-esta-chave-antes-de-compartilhar")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def get_db():
    if "db" not in g:
        DATA_DIR.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            program TEXT NOT NULL DEFAULT 'BIU MLP',
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message_template TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'opened', 'sent', 'skip')),
            opened_at TEXT,
            sent_at TEXT,
            UNIQUE(campaign_id, student_id),
            FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        );
    """)
    campaign_columns = {row[1] for row in db.execute("PRAGMA table_info(campaigns)")}
    if "status" not in campaign_columns:
        db.execute("ALTER TABLE campaigns ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
    db.commit()


def first_name(name):
    return " ".join(name.strip().split()).split(" ")[0] if name and name.strip() else ""


def clean_phone(value):
    return re.sub(r"\D", "", value or "")


def campaign_or_404(campaign_id):
    campaign = get_db().execute("SELECT * FROM campaigns WHERE id = ? AND archived_at IS NULL", (campaign_id,)).fetchone()
    if not campaign:
        return None
    return campaign


def add_student_to_open_campaigns(db, student_id):
    """Inclui um aluno novo em campanhas que ainda aceitam destinatários."""
    cursor = db.execute("""
        INSERT OR IGNORE INTO sends (campaign_id, student_id)
        SELECT id, ? FROM campaigns
        WHERE status = 'open' AND archived_at IS NULL
    """, (student_id,))
    return cursor.rowcount


@app.route("/")
def dashboard():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) FROM students WHERE active = 1").fetchone()[0]
    phone_ready = db.execute("SELECT COUNT(*) FROM students WHERE active = 1 AND phone IS NOT NULL AND phone != ''").fetchone()[0]
    campaigns = db.execute("""
        SELECT c.*, COUNT(s.id) AS total,
          SUM(CASE WHEN s.status = 'sent' THEN 1 ELSE 0 END) AS sent
        FROM campaigns c LEFT JOIN sends s ON s.campaign_id = c.id
        WHERE c.archived_at IS NULL GROUP BY c.id ORDER BY c.created_at DESC LIMIT 5
    """).fetchall()
    return render_template("dashboard.html", total_students=total_students, phone_ready=phone_ready, campaigns=campaigns)


@app.route("/students")
def students():
    rows = get_db().execute("SELECT * FROM students WHERE active = 1 ORDER BY full_name COLLATE NOCASE").fetchall()
    return render_template("students.html", students=rows)


@app.post("/students")
def add_student():
    full_name = request.form.get("full_name", "").strip()
    if not full_name:
        flash("Informe o nome completo do aluno.", "error")
        return redirect(url_for("students"))
    db = get_db()
    cursor = db.execute("INSERT INTO students (full_name, first_name, phone, email, program, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (full_name, first_name(full_name), clean_phone(request.form.get("phone")), request.form.get("email", "").strip(), request.form.get("program", "BIU MLP").strip() or "BIU MLP", request.form.get("notes", "").strip()))
    linked = add_student_to_open_campaigns(db, cursor.lastrowid)
    db.commit()
    suffix = f" Incluído em {linked} campanha(s) em andamento." if linked else ""
    flash(f"Aluno adicionado.{suffix}", "success")
    return redirect(url_for("students"))


@app.post("/students/<int:student_id>/edit")
def edit_student(student_id):
    full_name = request.form.get("full_name", "").strip()
    if not full_name:
        flash("O nome não pode ficar vazio.", "error")
        return redirect(url_for("students"))
    get_db().execute("UPDATE students SET full_name=?, first_name=?, phone=?, email=?, program=?, notes=? WHERE id=? AND active=1",
        (full_name, first_name(full_name), clean_phone(request.form.get("phone")), request.form.get("email", "").strip(), request.form.get("program", "BIU MLP").strip() or "BIU MLP", request.form.get("notes", "").strip(), student_id))
    get_db().commit()
    flash("Dados do aluno atualizados.", "success")
    return redirect(url_for("students"))


@app.post("/students/<int:student_id>/archive")
def archive_student(student_id):
    get_db().execute("UPDATE students SET active=0, archived_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), student_id))
    get_db().commit()
    flash("Aluno arquivado. O histórico foi preservado.", "success")
    return redirect(url_for("students"))


def read_sheet(upload):
    filename = upload.filename.lower()
    raw = upload.read()
    if filename.endswith(".csv"):
        text = raw.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(text)))
    if filename.endswith(".xlsx"):
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        return [list(row) for row in workbook.active.iter_rows(values_only=True)]
    raise ValueError("Use um arquivo .xlsx ou .csv.")


@app.route("/import", methods=["GET", "POST"])
def import_students():
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
    import json
    rows = json.loads(request.form.get("rows", "[]"))
    name_index = int(request.form.get("name_column", "-1"))
    if name_index < 0:
        flash("Escolha a coluna que contém os nomes.", "error")
        return redirect(url_for("import_students"))
    db = get_db()
    added = skipped = 0
    existing = {row[0].casefold() for row in db.execute("SELECT full_name FROM students WHERE active=1")}
    for row in rows:
        name = str(row[name_index] if name_index < len(row) else "").strip()
        normalized = " ".join(name.split())
        if not normalized or normalized.casefold() in existing:
            skipped += 1
            continue
        cursor = db.execute("INSERT INTO students (full_name, first_name) VALUES (?, ?)", (normalized, first_name(normalized)))
        add_student_to_open_campaigns(db, cursor.lastrowid)
        existing.add(normalized.casefold())
        added += 1
    db.commit()
    flash(f"Importação concluída: {added} aluno(s) adicionado(s); {skipped} linha(s) ignorada(s).", "success")
    return redirect(url_for("students"))


@app.route("/campaigns")
def campaigns():
    rows = get_db().execute("""
        SELECT c.*, COUNT(s.id) total, SUM(CASE WHEN s.status='sent' THEN 1 ELSE 0 END) sent
        FROM campaigns c LEFT JOIN sends s ON s.campaign_id=c.id
        WHERE c.archived_at IS NULL GROUP BY c.id ORDER BY c.created_at DESC
    """).fetchall()
    return render_template("campaigns.html", campaigns=rows)


@app.route("/campaigns/new", methods=["GET", "POST"])
def new_campaign():
    if request.method == "GET":
        return render_template("campaign_form.html")
    title, template = request.form.get("title", "").strip(), request.form.get("message_template", "").strip()
    if not title or not template:
        flash("Informe o título e a mensagem da campanha.", "error")
        return render_template("campaign_form.html", title=title, message_template=template)
    db = get_db()
    cur = db.execute("INSERT INTO campaigns (title, message_template) VALUES (?, ?)", (title, template))
    student_ids = db.execute("SELECT id FROM students WHERE active=1").fetchall()
    db.executemany("INSERT INTO sends (campaign_id, student_id) VALUES (?, ?)", [(cur.lastrowid, row[0]) for row in student_ids])
    db.commit()
    flash("Campanha criada.", "success")
    return redirect(url_for("campaign_detail", campaign_id=cur.lastrowid))


@app.route("/campaigns/<int:campaign_id>")
def campaign_detail(campaign_id):
    campaign = campaign_or_404(campaign_id)
    if not campaign:
        flash("Campanha não encontrada.", "error")
        return redirect(url_for("campaigns"))
    rows = get_db().execute("""
        SELECT s.*, se.status, se.opened_at, se.sent_at FROM sends se
        JOIN students s ON s.id=se.student_id WHERE se.campaign_id=? ORDER BY s.full_name COLLATE NOCASE
    """, (campaign_id,)).fetchall()
    return render_template("campaign_detail.html", campaign=campaign, students=rows, quote=quote)


@app.post("/campaigns/<int:campaign_id>/students/<int:student_id>/status")
def set_send_status(campaign_id, student_id):
    status = request.form.get("status")
    if status not in {"pending", "opened", "sent", "skip"}:
        flash("Situação inválida.", "error")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))
    now = datetime.now().isoformat(timespec="seconds")
    get_db().execute("UPDATE sends SET status=?, opened_at=CASE WHEN ?='opened' THEN ? ELSE opened_at END, sent_at=CASE WHEN ?='sent' THEN ? ELSE sent_at END WHERE campaign_id=? AND student_id=?", (status, status, now, status, now, campaign_id, student_id))
    get_db().commit()
    flash("Situação atualizada.", "success")
    return redirect(url_for("campaign_detail", campaign_id=campaign_id))


@app.post("/campaigns/<int:campaign_id>/sync")
def sync_campaign(campaign_id):
    campaign = campaign_or_404(campaign_id)
    if not campaign:
        flash("Campanha não encontrada.", "error")
        return redirect(url_for("campaigns"))
    if campaign["status"] != "open":
        flash("Apenas campanhas em andamento podem receber alunos novos.", "error")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))
    db = get_db()
    cursor = db.execute("""
        INSERT OR IGNORE INTO sends (campaign_id, student_id)
        SELECT ?, id FROM students WHERE active = 1
    """, (campaign_id,))
    db.commit()
    flash(f"Sincronização concluída: {cursor.rowcount} aluno(s) novo(s) incluído(s).", "success")
    return redirect(url_for("campaign_detail", campaign_id=campaign_id))


@app.post("/campaigns/<int:campaign_id>/status")
def set_campaign_status(campaign_id):
    status = request.form.get("status")
    if status not in {"open", "closed"}:
        flash("Situação inválida.", "error")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))
    db = get_db()
    db.execute("UPDATE campaigns SET status=? WHERE id=? AND archived_at IS NULL", (status, campaign_id))
    db.commit()
    message = "Campanha reaberta. Alunos novos voltarão a ser incluídos automaticamente." if status == "open" else "Campanha encerrada. O histórico foi preservado e novos alunos não serão incluídos."
    flash(message, "success")
    return redirect(url_for("campaign_detail", campaign_id=campaign_id))


@app.post("/campaigns/<int:campaign_id>/archive")
def archive_campaign(campaign_id):
    get_db().execute("UPDATE campaigns SET archived_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), campaign_id))
    get_db().commit()
    flash("Campanha arquivada. O histórico foi preservado.", "success")
    return redirect(url_for("campaigns"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
