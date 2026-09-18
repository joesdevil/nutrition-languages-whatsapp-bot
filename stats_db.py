import sqlite3
from datetime import datetime


DB_FILE = "stats.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# GET TRAINED EXERCISE FILENAMES
# ============================================================

def get_trained_exercise_filenames(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT we.filename
        FROM workout_exercises we
        JOIN workout_sessions ws
            ON we.session_id = ws.id
        WHERE ws.user_id = ?
          AND we.filename IS NOT NULL
          AND we.filename != ''
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return {
        str(row["filename"]).strip().lower()
        for row in rows
    }

# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    conn = get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            meal_type TEXT,
            eaten_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            fdc_id INTEGER,
            quantity REAL,
            unit TEXT,
            calories REAL,
            protein REAL,
            carbs REAL,
            fat REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (meal_id)
                REFERENCES meals(id)
        );
        
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            training_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workout_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            filename TEXT,
            target TEXT,
            completed_at TEXT NOT NULL,

            FOREIGN KEY (session_id)
            REFERENCES workout_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS pending_workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            target TEXT,
            count INTEGER,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS exercise_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_exercise_id INTEGER NOT NULL,
            set_number INTEGER NOT NULL,
            weight REAL,
            reps INTEGER,
            duration_seconds INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (workout_exercise_id)
                REFERENCES workout_exercises(id)
        );
        CREATE TABLE IF NOT EXISTS pending_exercise_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pending_exercise_id INTEGER NOT NULL,
            set_number INTEGER NOT NULL,
            weight REAL,
            reps INTEGER,
            duration_seconds INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (pending_exercise_id)
                REFERENCES pending_exercises(id)
        );

        CREATE TABLE IF NOT EXISTS pending_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pending_workout_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            filename TEXT,
            target TEXT,
            sent_at TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            sets_count INTEGER,
            FOREIGN KEY (pending_workout_id)
                REFERENCES pending_workouts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user
        ON workout_sessions(user_id);

        CREATE INDEX IF NOT EXISTS idx_exercises_session
        ON workout_exercises(session_id);

        CREATE INDEX IF NOT EXISTS idx_pending_user
        ON pending_workouts(user_id);
    """)

    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(pending_exercises)")
    ]

    if "sets_count" not in columns:
        conn.execute(
            "ALTER TABLE pending_exercises ADD COLUMN sets_count INTEGER"
        )
    conn.commit()
    
    conn.close()


def create_meal(
    user_id,
    meal_type=None,
    eaten_at=None
):
    conn = get_connection()

    now = datetime.now()

    if eaten_at is None:
        eaten_at = now.isoformat(timespec="seconds")

    created_at = now.isoformat(timespec="seconds")

    cursor = conn.execute(
        """
        INSERT INTO meals (
            user_id,
            meal_type,
            eaten_at,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            meal_type,
            eaten_at,
            created_at
        )
    )

    meal_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return meal_id


def add_meal_item(
    meal_id,
    food_name,
    fdc_id=None,
    quantity=None,
    unit=None,
    calories=None,
    protein=None,
    carbs=None,
    fat=None
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO meal_items (
            meal_id,
            food_name,
            fdc_id,
            quantity,
            unit,
            calories,
            protein,
            carbs,
            fat,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meal_id,
            food_name,
            fdc_id,
            quantity,
            unit,
            calories,
            protein,
            carbs,
            fat,
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conn.commit()
    conn.close()
    
    
def get_daily_nutrition(user_id, date=None):
    conn = get_connection()

    if date is None:
        date = datetime.now().date().isoformat()

    row = conn.execute(
        """
        SELECT
            COUNT(DISTINCT m.id) AS meals,
            COALESCE(SUM(mi.calories), 0) AS calories,
            COALESCE(SUM(mi.protein), 0) AS protein,
            COALESCE(SUM(mi.carbs), 0) AS carbs,
            COALESCE(SUM(mi.fat), 0) AS fat
        FROM meals m
        JOIN meal_items mi
            ON mi.meal_id = m.id
        WHERE m.user_id = ?
          AND DATE(m.eaten_at) = ?
        """,
        (
            user_id,
            date
        )
    ).fetchone()

    conn.close()

    return {
        "meals": row["meals"],
        "calories": round(row["calories"], 2),
        "protein": round(row["protein"], 2),
        "carbs": round(row["carbs"], 2),
        "fat": round(row["fat"], 2)
    }

def get_pending_exercise(user_id, exercise_name=None):
    conn = get_connection()

    if exercise_name:
        row = conn.execute(
            """
            SELECT pe.*
            FROM pending_exercises pe
            JOIN pending_workouts pw
                ON pe.pending_workout_id = pw.id
            WHERE pw.user_id = ?
              AND pw.status = 'pending'
              AND pe.completed = 0
              AND LOWER(pe.exercise_name) = LOWER(?)
            ORDER BY pe.id DESC
            LIMIT 1
            """,
            (user_id, exercise_name)
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT pe.*
            FROM pending_exercises pe
            JOIN pending_workouts pw
                ON pe.pending_workout_id = pw.id
            WHERE pw.user_id = ?
              AND pw.status = 'pending'
              AND pe.completed = 0
            ORDER BY pe.id
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

    conn.close()
    return row


def get_nutrition_by_date(user_id, date):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            COUNT(DISTINCT m.id) AS meals,
            COALESCE(SUM(mi.calories), 0) AS calories,
            COALESCE(SUM(mi.protein), 0) AS protein,
            COALESCE(SUM(mi.carbs), 0) AS carbs,
            COALESCE(SUM(mi.fat), 0) AS fat
        FROM meals m
        JOIN meal_items mi
            ON mi.meal_id = m.id
        WHERE m.user_id = ?
          AND DATE(m.eaten_at) = ?
        """,
        (
            user_id,
            date
        )
    ).fetchone()

    conn.close()

    return {
        "meals": row["meals"],
        "calories": round(row["calories"], 2),
        "protein": round(row["protein"], 2),
        "carbs": round(row["carbs"], 2),
        "fat": round(row["fat"], 2)
    }
    
def get_exercises_by_date(user_id, date):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            ws.training_date,
            we.exercise_name,
            we.target
        FROM workout_sessions ws
        JOIN workout_exercises we
            ON we.session_id = ws.id
        WHERE ws.user_id = ?
          AND ws.training_date = ?
        ORDER BY we.id
        """,
        (
            user_id,
            date
        )
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def add_exercise_set(
    pending_exercise_id,
    set_number,
    weight=None,
    reps=None,
    duration_seconds=None
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO pending_exercise_sets (
            pending_exercise_id,
            set_number,
            weight,
            reps,
            duration_seconds,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            pending_exercise_id,
            set_number,
            weight,
            reps,
            duration_seconds,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()
    
# ============================================================
# START NEW PENDING WORKOUT
# ============================================================

def start_pending_workout(
    user_id,
    target=None,
    count=None
):

    conn = get_connection()

    # Replace any old pending workout.
    conn.execute("""
        UPDATE pending_workouts
        SET status = 'replaced'
        WHERE user_id = ?
        AND status = 'pending'
    """, (user_id,))

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor = conn.execute("""
        INSERT INTO pending_workouts
        (
            user_id,
            target,
            count,
            created_at,
            status
        )
        VALUES (?, ?, ?, ?, 'pending')
    """, (
        user_id,
        target,
        count,
        now
    ))

    pending_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return pending_id


def set_exercise_sets_count(pending_exercise_id, sets_count):
    conn = get_connection()

    conn.execute(
        """
        UPDATE pending_exercises
        SET sets_count = ?
        WHERE id = ?
        """,
        (sets_count, pending_exercise_id)
    )

    conn.commit()
    conn.close()
    
def get_pending_exercise_sets(pending_exercise_id):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM pending_exercise_sets
        WHERE pending_exercise_id = ?
        ORDER BY set_number
        """,
        (pending_exercise_id,)
    ).fetchall()

    conn.close()
    return rows

def complete_pending_exercise(pending_exercise_id):
    conn = get_connection()

    conn.execute(
        """
        UPDATE pending_exercises
        SET completed = 1
        WHERE id = ?
        """,
        (pending_exercise_id,)
    )

    conn.commit()
    conn.close()
    
# ============================================================
# ADD SENT EXERCISE TO PENDING WORKOUT
# ============================================================

def add_pending_exercise(
    pending_workout_id,
    exercise_name,
    filename=None,
    target=None
):
    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO pending_exercises (
            pending_workout_id,
            exercise_name,
            filename,
            target,
            sent_at,
            completed
        )
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (
            pending_workout_id,
            exercise_name,
            filename,
            target,
            datetime.now().isoformat()
        )
    )

    pending_exercise_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return pending_exercise_id

# ============================================================
# GET CURRENT PENDING WORKOUT
# ============================================================

def get_pending_workout(user_id):

    conn = get_connection()

    workout = conn.execute("""
        SELECT *
        FROM pending_workouts

        WHERE user_id = ?
        AND status = 'pending'

        ORDER BY id DESC
        LIMIT 1
    """, (user_id,)).fetchone()

    if not workout:

        conn.close()

        return None

    exercises = conn.execute("""
        SELECT *
        FROM pending_exercises

        WHERE pending_workout_id = ?
        AND completed = 0

        ORDER BY id ASC
    """, (
        workout["id"],
    )).fetchall()

    conn.close()

    return {
        "id": workout["id"],
        "user_id": workout["user_id"],
        "target": workout["target"],
        "count": workout["count"],
        "exercises": [
            dict(row)
            for row in exercises
        ]
    }


# ============================================================
# COMPLETE PENDING WORKOUT
# ============================================================

def complete_pending_workout(user_id):

    pending = get_pending_workout(
        user_id
    )

    if not pending:

        return None

    if not pending["exercises"]:

        return None

    conn = get_connection()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    training_date = datetime.now().date().isoformat()

    # --------------------------------------------------------
    # CREATE PERMANENT WORKOUT SESSION
    # --------------------------------------------------------

    cursor = conn.execute("""
        INSERT INTO workout_sessions
        (
            user_id,
            training_date,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        training_date,
        now
    ))

    session_id = cursor.lastrowid

    # --------------------------------------------------------
    # SAVE EXERCISES
    # --------------------------------------------------------

    # --------------------------------------------------------
    # SAVE EXERCISES + SETS
    # --------------------------------------------------------

    for exercise in pending["exercises"]:

        cursor = conn.execute("""
            INSERT INTO workout_exercises
            (
                session_id,
                exercise_name,
                filename,
                target,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            exercise["exercise_name"],
            exercise["filename"],
            exercise["target"],
            now
        ))

        # ID of the newly created permanent exercise
        workout_exercise_id = cursor.lastrowid

        # ----------------------------------------------------
        # COPY SETS FROM PENDING TO PERMANENT
        # ----------------------------------------------------

        pending_sets = conn.execute("""
            SELECT
                set_number,
                weight,
                reps,
                duration_seconds,
                created_at
            FROM pending_exercise_sets
            WHERE pending_exercise_id = ?
            ORDER BY set_number
        """, (
            exercise["id"],
        )).fetchall()

        for set_row in pending_sets:

            conn.execute("""
                INSERT INTO exercise_sets
                (
                    workout_exercise_id,
                    set_number,
                    weight,
                    reps,
                    duration_seconds,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                workout_exercise_id,
                set_row["set_number"],
                set_row["weight"],
                set_row["reps"],
                set_row["duration_seconds"],
                set_row["created_at"]
            ))

        # ----------------------------------------------------
        # MARK PENDING EXERCISE COMPLETE
        # ----------------------------------------------------

        conn.execute("""
            UPDATE pending_exercises
            SET completed = 1
            WHERE id = ?
        """, (
            exercise["id"],
        ))
    # --------------------------------------------------------
    # MARK PENDING WORKOUT COMPLETE
    # --------------------------------------------------------

    conn.execute("""
        UPDATE pending_workouts

        SET status = 'completed'

        WHERE id = ?
    """, (
        pending["id"],
    ))

    conn.commit()
    conn.close()

    return {
        "session_id": session_id,

        "count": len(
            pending["exercises"]
        ),

        "exercises": [
            exercise["exercise_name"]
            for exercise
            in pending["exercises"]
        ]
    }


# ============================================================
# GET OVERALL STATS
# ============================================================

# def get_stats(user_id):

#     conn = get_connection()

#     total_days = conn.execute("""
#         SELECT COUNT(
#             DISTINCT training_date
#         )

#         FROM workout_sessions

#         WHERE user_id = ?
#     """, (
#         user_id,
#     )).fetchone()[0]

#     total_exercises = conn.execute("""
#         SELECT COUNT(*)

#         FROM workout_exercises we

#         JOIN workout_sessions ws
#         ON ws.id = we.session_id

#         WHERE ws.user_id = ?
#     """, (
#         user_id,
#     )).fetchone()[0]

#     recent_sessions = conn.execute("""
#         SELECT
#             ws.training_date,
#             GROUP_CONCAT(
#                 we.exercise_name,
#                 ', '
#             ) AS exercises

#         FROM workout_sessions ws

#         JOIN workout_exercises we
#         ON we.session_id = ws.id

#         WHERE ws.user_id = ?

#         GROUP BY
#             ws.id,
#             ws.training_date

#         ORDER BY
#             ws.training_date DESC,
#             ws.id DESC

#         LIMIT 10
#     """, (
#         user_id,
#     )).fetchall()

#     conn.close()

#     return {
#         "total_days": total_days,

#         "total_exercises":
#             total_exercises,

#         "recent_sessions": [
#             dict(row)
#             for row in recent_sessions
#         ]
#     }


# ============================================================
# GET OVERALL STATS
# ============================================================

def get_stats(user_id):

    conn = get_connection()

    # --------------------------------------------------------
    # TOTAL TRAINING DAYS
    # --------------------------------------------------------

    total_days = conn.execute("""
        SELECT COUNT(
            DISTINCT training_date
        )
        FROM workout_sessions
        WHERE user_id = ?
    """, (
        user_id,
    )).fetchone()[0]

    # --------------------------------------------------------
    # TOTAL EXERCISES
    # --------------------------------------------------------

    total_exercises = conn.execute("""
        SELECT COUNT(*)
        FROM workout_exercises we
        JOIN workout_sessions ws
            ON ws.id = we.session_id
        WHERE ws.user_id = ?
    """, (
        user_id,
    )).fetchone()[0]

    # --------------------------------------------------------
    # RECENT WORKOUTS
    #
    # Group ALL exercises from the same date together.
    # --------------------------------------------------------

    recent_sessions = conn.execute("""
        SELECT
            ws.id AS session_id,
            ws.training_date,
            we.id AS workout_exercise_id,
            we.exercise_name,
            es.set_number,
            es.weight,
            es.reps,
            es.duration_seconds

        FROM workout_sessions ws

        JOIN workout_exercises we
            ON we.session_id = ws.id

        LEFT JOIN exercise_sets es
            ON es.workout_exercise_id = we.id

        WHERE ws.user_id = ?

        ORDER BY
            ws.training_date DESC,
            ws.id DESC,
            we.id ASC,
            es.set_number ASC

        LIMIT 100
    """, (
        user_id,
    )).fetchall()

    conn.close()

    return {
        "total_days": total_days,

        "total_exercises": total_exercises,

        "recent_sessions": [
            dict(row)
            for row in recent_sessions
        ]
    }


# ============================================================
# GET EXERCISES FOR PERIOD
# ============================================================

def get_exercises_by_period(
    user_id,
    days=7
):

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            ws.training_date,
            we.exercise_name,
            we.target

        FROM workout_sessions ws

        JOIN workout_exercises we
        ON we.session_id = ws.id

        WHERE ws.user_id = ?

        AND ws.training_date >= date(
            'now',
            ?
        )

        ORDER BY
            ws.training_date DESC,
            ws.id DESC,
            we.id ASC
    """, (
        user_id,
        f"-{int(days) - 1} days"
    )).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# GET MUSCLE STATS
# ============================================================

def get_muscle_stats(
    user_id,
    target
):

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            ws.training_date,
            we.exercise_name

        FROM workout_sessions ws

        JOIN workout_exercises we
        ON we.session_id = ws.id

        WHERE ws.user_id = ?

        AND LOWER(
            COALESCE(
                we.target,
                ''
            )
        ) = LOWER(?)

        ORDER BY
            ws.training_date DESC,
            we.id DESC
    """, (
        user_id,
        target
    )).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# INITIALIZE AUTOMATICALLY
# ============================================================

init_db()