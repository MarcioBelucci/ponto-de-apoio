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
    return [dict(day=row["day"], day_name=ACTIVITIES[row["day"]][0],
                 activity=ACTIVITIES[row["day"]][1], target=row["target"],
                 completed=row["completed"]) for row in rows]


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
