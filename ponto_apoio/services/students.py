"""Regras de negócio e importação de alunos."""

import csv
import io
import re
import unicodedata

from openpyxl import load_workbook

from ponto_apoio.services.campaigns import add_student_to_open_campaigns


def first_name(name):
    """Extrai o primeiro nome de um nome completo."""
    normalized = " ".join((name or "").strip().split())
    return normalized.split(" ")[0] if normalized else ""


def clean_phone(value):
    """Valida um telefone opcional em formato internacional para o WhatsApp."""
    value = (value or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"\+?[0-9 ()-]+", value):
        raise ValueError("Telefone inválido. Use DDI, DDD e número, apenas com números e formatação comum.")
    digits = re.sub(r"\D", "", value)
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValueError("Telefone inválido. Informe o número internacional com DDI, entre 8 e 15 dígitos.")
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
    db.execute(
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


def archive_student(db, student_id, archived_at):
    """Arquiva um aluno sem apagar o histórico de envios."""
    db.execute(
        "UPDATE students SET active=0, archived_at=? WHERE id=?",
        (archived_at, student_id),
    )


def restore_student(db, student_id):
    """Reativa o aluno e o inclui nos outreaches abertos, sem duplicar registros."""
    cursor = db.execute(
        "UPDATE students SET active=1, archived_at=NULL WHERE id=? AND active=0",
        (student_id,),
    )
    if not cursor.rowcount:
        return None
    return add_student_to_open_campaigns(db, student_id)


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


def import_students(db, rows, name_index):
    """Importa nomes únicos e retorna as quantidades adicionadas e ignoradas."""
    existing = {
        row[0].casefold()
        for row in db.execute("SELECT full_name FROM students WHERE active=1")
    }
    added = skipped = 0
    for row in rows:
        name = str(row[name_index] if name_index < len(row) else "").strip()
        normalized_name = " ".join(name.split())
        if not normalized_name or normalized_name.casefold() in existing:
            skipped += 1
            continue
        add_student(db, normalized_name)
        existing.add(normalized_name.casefold())
        added += 1
    return added, skipped
