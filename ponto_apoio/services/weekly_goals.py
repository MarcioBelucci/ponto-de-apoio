"""Metas e progresso de cada semana, separados do controle de outreaches."""

from datetime import date, timedelta

ACTIVITIES = (
    ("Segunda-feira", "Outreaches personalizados", 5),
    ("Terça-feira", "Outreaches personalizados", 5),
    ("Quarta-feira", "Convites para reunião", 3),
    ("Quinta-feira", "Mensagens de parabéns", 5),
)


def monday(day):
    return day - timedelta(days=day.weekday())


def ensure_week(db, week):
    db.executemany(
        "INSERT OR IGNORE INTO weekly_goals (week_start, day, target) VALUES (?, ?, ?)",
        [(week.isoformat(), index, activity[2]) for index, activity in enumerate(ACTIVITIES)],
    )
    db.commit()


def week_summary(db, week):
    rows = db.execute(
        "SELECT day, target, completed FROM weekly_goals WHERE week_start=? ORDER BY day",
        (week.isoformat(),),
    ).fetchall()
    result = []
    for row in rows:
        contacts = db.execute("""SELECT wc.id, s.full_name, s.active FROM weekly_contacts wc
            JOIN students s ON s.id=wc.student_id WHERE wc.week_start=? AND wc.day=?
            ORDER BY s.full_name COLLATE NOCASE""", (week.isoformat(), row['day'])).fetchall()
        result.append(dict(day=row['day'], day_name=ACTIVITIES[row['day']][0],
                           activity=ACTIVITIES[row['day']][1], target=row['target'],
                           completed=row['completed'] + len(contacts), legacy=row['completed'], contacts=contacts))
    return result


def add_contact(db, week, day, student_id):
    cursor = db.execute("""INSERT OR IGNORE INTO weekly_contacts (week_start, day, student_id)
        SELECT g.week_start, g.day, s.id FROM weekly_goals g JOIN students s ON s.id=? AND s.active=1
        WHERE g.week_start=? AND g.day=? AND g.completed +
        (SELECT COUNT(*) FROM weekly_contacts c WHERE c.week_start=g.week_start AND c.day=g.day) < g.target""",
        (student_id, week.isoformat(), day))
    return cursor.rowcount > 0


def remove_contact(db, week, contact_id):
    return db.execute('DELETE FROM weekly_contacts WHERE id=? AND week_start=?',
                      (contact_id, week.isoformat())).rowcount > 0


def change_count(db, week, day, delta):
    cursor = db.execute(
        """UPDATE weekly_goals SET completed=completed + ?
           WHERE week_start=? AND day=?
           AND ((? = 1 AND completed < target) OR (? = -1 AND completed > 0))""",
        (delta, week.isoformat(), day, delta, delta),
    )
    return cursor.rowcount > 0


def set_targets(db, week, targets):
    db.executemany("UPDATE weekly_goals SET target=? WHERE week_start=? AND day=?",
                   [(target, week.isoformat(), day) for day, target in enumerate(targets)])
