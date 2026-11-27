"""Regras de negócio e importação de alunos."""

import csv
import io
import json
import re
import unicodedata

from openpyxl import load_workbook

from ponto_apoio.services.campaigns import add_student_to_open_campaigns


def first_name(name):
    """Extrai o primeiro nome de um nome completo."""
    normalized = " ".join((name or "").strip().split())
    return normalized.split(" ")[0] if normalized else ""


def clean_phone(value):
    """Mantém os dígitos de um telefone opcional, sem impor regras por país."""
    value = (value or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"\+?[0-9 ()-]+", value):
        raise ValueError("Telefone inválido. Use números e os símbolos +, espaços, parênteses ou hífens.")
    digits = re.sub(r"\D", "", value)
    if not digits:
        raise ValueError("Telefone inválido. Informe ao menos um número.")
    return digits


def duplicate_student(db, full_name, exclude_id=None):
    """Identifica nomes iguais entre alunos ativos, desconsiderando espaços e caixa."""
    normalized = " ".join(full_name.split()).casefold()
    return next((row for row in list_active_students(db)
                 if row['id'] != exclude_id and ' '.join(row['full_name'].split()).casefold() == normalized), None)


def normalize_search(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c))


def list_students(db, search="", archived=False):
    students = db.execute(
        "SELECT * FROM students WHERE active = ? ORDER BY full_name COLLATE NOCASE", (0 if archived else 1,)
    ).fetchall()
    terms = normalize_search(search).split()
    return [student for student in students
            if all(term in normalize_search(student['full_name']) for term in terms)]


def list_active_students(db, search=""):
    return list_students(db, search)


def student_history(db, student_id):
    """Retorna a participação em outreaches e os contatos de metas do aluno."""
    campaigns = db.execute("""
        SELECT c.id, c.title, c.created_at, c.archived_at, se.status, se.sent_at
        FROM sends se JOIN campaigns c ON c.id=se.campaign_id
        WHERE se.student_id=?
        ORDER BY c.created_at DESC, c.id DESC
    """, (student_id,)).fetchall()
    contacts = db.execute("""
        SELECT week_start, day, created_at FROM weekly_contacts
        WHERE student_id=? ORDER BY week_start DESC, day DESC, id DESC
    """, (student_id,)).fetchall()
    return campaigns, contacts


def add_student(db, full_name, phone="", email="", program="BIU MLP", notes=""):
    """Cria um aluno e o inclui nos outreaches em andamento."""
    normalized_name = " ".join(full_name.strip().split())
    cursor = db.execute(
        """
        INSERT INTO students (full_name, first_name, phone, email, program, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_name,
            first_name(normalized_name),
            clean_phone(phone),
            email.strip(),
            program.strip() or "BIU MLP",
            notes.strip(),
        ),
    )
    linked_campaigns = add_student_to_open_campaigns(db, cursor.lastrowid)
    return linked_campaigns


def update_student(db, student_id, full_name, phone, email, program, notes):
    """Atualiza as informações editáveis de um aluno ativo."""
    normalized_name = " ".join(full_name.strip().split())
    cursor = db.execute(
        """
        UPDATE students
        SET full_name=?, first_name=?, phone=?, email=?, program=?, notes=?
        WHERE id=? AND active=1
        """,
        (
            normalized_name,
            first_name(normalized_name),
            clean_phone(phone),
            email.strip(),
            program.strip() or "BIU MLP",
            notes.strip(),
            student_id,
        ),
    )
    return cursor.rowcount > 0


def archive_student(db, student_id, archived_at):
    """Arquiva um aluno sem apagar o histórico de envios."""
    return db.execute(
        "UPDATE students SET active=0, archived_at=? WHERE id=? AND active=1",
        (archived_at, student_id),
    ).rowcount > 0


def restore_student(db, student_id):
    """Reativa o aluno e o inclui nos outreaches abertos, sem duplicar registros."""
    cursor = db.execute(
        "UPDATE students SET active=1, archived_at=NULL WHERE id=? AND active=0 AND merged_into IS NULL",
        (student_id,),
    )
    if not cursor.rowcount:
        return None
    return add_student_to_open_campaigns(db, student_id)


def merge_candidates(db, source_id):
    source = db.execute("SELECT * FROM students WHERE id=? AND active=0 AND merged_into IS NULL", (source_id,)).fetchone()
    if not source:
        return None, []
    key = " ".join(source["full_name"].split()).casefold()
    candidates = [row for row in list_active_students(db) if " ".join(row["full_name"].split()).casefold() == key]
    return source, candidates


def merge_students(db, source_id, target_id):
    """Une um arquivado a um ativo, guardando cópia dos registros originais."""
    source, candidates = merge_candidates(db, source_id)
    target = next((row for row in candidates if row["id"] == target_id), None)
    if not target:
        return False
    source_sends = db.execute("SELECT * FROM sends WHERE student_id=?", (source_id,)).fetchall()
    target_sends = db.execute("SELECT * FROM sends WHERE student_id=?", (target_id,)).fetchall()
    source_contacts = db.execute("SELECT * FROM weekly_contacts WHERE student_id=?", (source_id,)).fetchall()
    target_contacts = db.execute("SELECT * FROM weekly_contacts WHERE student_id=?", (target_id,)).fetchall()
    snapshot = dict(source=dict(source), target=dict(target),
                    source_sends=[dict(row) for row in source_sends],
                    target_sends=[dict(row) for row in target_sends],
                    source_contacts=[dict(row) for row in source_contacts],
                    target_contacts=[dict(row) for row in target_contacts])
    db.execute("INSERT INTO student_merges (source_id, target_id, snapshot) VALUES (?, ?, ?)",
               (source_id, target_id, json.dumps(snapshot, ensure_ascii=False)))
    for send in source_sends:
        other = db.execute("SELECT * FROM sends WHERE campaign_id=? AND student_id=?", (send["campaign_id"], target_id)).fetchone()
        if not other:
            db.execute("UPDATE sends SET student_id=? WHERE id=?", (target_id, send["id"]))
        else:
            status = "sent" if "sent" in (send["status"], other["status"]) else other["status"]
            sent_at = (other["sent_at"] if other["status"] == "sent" else send["sent_at"]) if status == "sent" else (other["sent_at"] or send["sent_at"])
            db.execute("UPDATE sends SET status=?, sent_at=?, opened_at=? WHERE id=?",
                       (status, sent_at, other["opened_at"] or send["opened_at"], other["id"]))
            db.execute("DELETE FROM sends WHERE id=?", (send["id"],))
    for contact in source_contacts:
        other = db.execute("SELECT id FROM weekly_contacts WHERE week_start=? AND day=? AND student_id=?",
                           (contact["week_start"], contact["day"], target_id)).fetchone()
        if other:
            db.execute("DELETE FROM weekly_contacts WHERE id=?", (contact["id"],))
        else:
            db.execute("UPDATE weekly_contacts SET student_id=? WHERE id=?", (target_id, contact["id"]))
    db.execute("UPDATE students SET merged_into=? WHERE id=?", (target_id, source_id))
    return True


def read_sheet(upload):
    """Lê uma planilha CSV ou XLSX enviada pelo usuário."""
    filename = upload.filename.lower()
    raw = upload.read()
    if filename.endswith(".csv"):
        return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    if filename.endswith(".xlsx"):
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        return [list(row) for row in workbook.active.iter_rows(values_only=True)]
    raise ValueError("Use um arquivo .xlsx ou .csv.")


def import_students(db, rows, name_index, phone_index=None, email_index=None, errors=None):
    """Importa alunos novos; contatos inválidos fazem a linha ser ignorada."""
    existing = {
        row[0].casefold()
        for row in db.execute("SELECT full_name FROM students WHERE active=1")
    }
    archived_names = {
        " ".join(row[0].split()).casefold()
        for row in db.execute("SELECT full_name FROM students WHERE active=0")
    }
    added = skipped = 0
    for line_number, row in enumerate(rows, start=2):
        name = str(row[name_index] or "").strip() if name_index < len(row) else ""
        normalized_name = " ".join(name.split())
        if not normalized_name:
            skipped += 1
            continue
        if normalized_name.casefold() in archived_names:
            if errors is not None:
                errors.append(f"Linha {line_number}: nome também encontrado em alunos arquivados; confira antes de reativar ou cadastrar.")
            skipped += 1
            continue
        if normalized_name.casefold() in existing:
            skipped += 1
            continue
        phone = str(row[phone_index] or "").strip() if phone_index is not None and phone_index < len(row) else ""
        # Algumas planilhas exportam números inteiros como texto terminado em .0.
        if re.fullmatch(r"[0-9]+\.0+", phone):
            phone = phone.split(".", 1)[0]
        email = str(row[email_index] or "").strip() if email_index is not None and email_index < len(row) else ""
        try:
            phone = clean_phone(phone)
        except ValueError:
            if errors is not None:
                errors.append(f"Linha {line_number}: telefone inválido; use números e formatação comum.")
            skipped += 1
            continue
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            if errors is not None:
                errors.append(f"Linha {line_number}: e-mail inválido.")
            skipped += 1
            continue
        add_student(db, normalized_name, phone=phone, email=email)
        existing.add(normalized_name.casefold())
        added += 1
    return added, skipped
