"""Regras de negócio para outreaches e envios."""


def campaign_by_id(db, campaign_id, include_archived=False):
    return db.execute(
        "SELECT * FROM campaigns WHERE id = ? AND (archived_at IS NULL OR ? = 1)", (campaign_id, include_archived)
    ).fetchone()


def add_student_to_open_campaigns(db, student_id):
    """Inclui um aluno em todos os outreaches abertos, sem duplicar envios."""
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO sends (campaign_id, student_id)
        SELECT id, ? FROM campaigns
        WHERE status = 'open' AND archived_at IS NULL
        """,
        (student_id,),
    )
    return cursor.rowcount


def list_campaigns(db, limit=None, status="all", archived=False, search=""):
    from ponto_apoio.services.students import normalize_search
    query = """
        SELECT c.*, COUNT(s.id) AS total,
               SUM(CASE WHEN s.status = 'sent' THEN 1 ELSE 0 END) AS sent
        FROM campaigns c
        LEFT JOIN sends s ON s.campaign_id = c.id
        WHERE (c.archived_at IS NOT NULL) = ? AND (? = 'all' OR c.status = ?)
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """
    params = [int(archived), status, status]
    if limit is not None and not search:
        query += " LIMIT ?"
        params.append(limit)
    rows = db.execute(query, params).fetchall()
    terms = normalize_search(search).split()
    rows = [row for row in rows if all(term in normalize_search(row['title']) for term in terms)]
    return rows[:limit] if limit is not None else rows


def create_campaign(db, title, message_template):
    """Cria um outreach e atribui os alunos ativos existentes."""
    cursor = db.execute(
        "INSERT INTO campaigns (title, message_template) VALUES (?, ?)",
        (title, message_template),
    )
    campaign_id = cursor.lastrowid
    db.execute(
        """
        INSERT INTO sends (campaign_id, student_id)
        SELECT ?, id FROM students WHERE active = 1
        """,
        (campaign_id,),
    )
    return campaign_id


def list_campaign_students(db, campaign_id):
    return db.execute(
        """
        SELECT s.*, se.status, se.opened_at, se.sent_at
        FROM sends se
        JOIN students s ON s.id = se.student_id
        WHERE se.campaign_id = ?
        ORDER BY s.full_name COLLATE NOCASE
        """,
        (campaign_id,),
    ).fetchall()


def set_send_status(db, campaign_id, student_id, status, timestamp):
    """Atualiza o status de um destinatário e registra os horários relevantes."""
    db.execute(
        """
        UPDATE sends
        SET status=?,
            opened_at=CASE WHEN ?='opened' THEN ? ELSE opened_at END,
            sent_at=CASE WHEN ?='sent' THEN ? ELSE sent_at END
        WHERE campaign_id=? AND student_id=?
        """,
        (status, status, timestamp, status, timestamp, campaign_id, student_id),
    )


def sync_campaign(db, campaign_id):
    """Inclui todos os alunos ativos que ainda não estão no outreach."""
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO sends (campaign_id, student_id)
        SELECT ?, id FROM students WHERE active = 1
        """,
        (campaign_id,),
    )
    return cursor.rowcount


def set_campaign_status(db, campaign_id, status):
    db.execute(
        "UPDATE campaigns SET status=? WHERE id=? AND archived_at IS NULL",
        (status, campaign_id),
    )


def archive_campaign(db, campaign_id, archived_at):
    db.execute(
        "UPDATE campaigns SET archived_at=? WHERE id=?", (archived_at, campaign_id)
    )


def restore_campaign(db, campaign_id):
    """Restaura o histórico como encerrado, sem alterar os destinatários."""
    return db.execute(
        "UPDATE campaigns SET archived_at=NULL, status='closed' WHERE id=? AND archived_at IS NOT NULL",
        (campaign_id,),
    ).rowcount > 0
