import sqlite3
from datetime import datetime


DB_PATH = "stats.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_language_tables():
    """
    Create language-learning tables if they do not exist.

    vocabulary:
        Stores the actual vocabulary words and their
        enriched information.

    learned_words:
        Stores user-specific learning/review information.
    """

    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            language TEXT NOT NULL,
            level TEXT NOT NULL,
            word TEXT NOT NULL,

            translation TEXT,
            definition TEXT,
            part_of_speech TEXT,
            pronunciation TEXT,

            example_sentence TEXT,
            example_translation TEXT,

            source TEXT,
            source_id TEXT,

            created_at TEXT NOT NULL,

            UNIQUE(language, level, word)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS learned_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id TEXT NOT NULL,
            vocabulary_id INTEGER NOT NULL,

            first_seen TEXT NOT NULL,
            last_reviewed TEXT,

            next_review TEXT,

            review_count INTEGER DEFAULT 0,
            mastery INTEGER DEFAULT 0,

            FOREIGN KEY (vocabulary_id)
                REFERENCES vocabulary(id),

            UNIQUE(user_id, vocabulary_id)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS language_preferences (
            user_id TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS language_quiz_sessions (
            user_id TEXT PRIMARY KEY,
            vocabulary_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (vocabulary_id)
                REFERENCES vocabulary(id)
        )
    """)

    conn.commit()
    conn.close()


def save_vocabulary(
    language,
    level,
    word,
    translation=None,
    definition=None,
    part_of_speech=None,
    pronunciation=None,
    example_sentence=None,
    example_translation=None,
    source=None,
    source_id=None
):
    """
    Insert a vocabulary word or update the existing word.

    Duplicate protection:
        UNIQUE(language, level, word)

    If the word already exists, its enriched information
    is updated instead of inserting another row.

    Returns:
        vocabulary_id
    """

    conn = get_connection()

    existing = conn.execute("""
        SELECT id
        FROM vocabulary
        WHERE language = ?
        AND level = ?
        AND word = ?
    """, (
        language,
        level,
        word
    )).fetchone()

    if existing:

        vocabulary_id = existing["id"]

        conn.execute("""
            UPDATE vocabulary
            SET
                translation = ?,
                definition = ?,
                part_of_speech = ?,
                pronunciation = ?,
                example_sentence = ?,
                example_translation = ?,
                source = ?,
                source_id = ?
            WHERE id = ?
        """, (
            translation,
            definition,
            part_of_speech,
            pronunciation,
            example_sentence,
            example_translation,
            source,
            source_id,
            vocabulary_id
        ))
        
    else:

        cursor = conn.execute("""
            INSERT INTO vocabulary (
                language,
                level,
                word,
                translation,
                definition,
                part_of_speech,
                pronunciation,
                example_sentence,
                example_translation,
                source,
                source_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            language,
            level,
            word,
            translation,
            definition,
            part_of_speech,
            pronunciation,
            example_sentence,
            example_translation,
            source,
            source_id,
            datetime.now().isoformat()
        ))

        vocabulary_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return vocabulary_id


def get_vocabulary(
    language,
    level,
    word
):
    """
    Get one vocabulary word.
    """

    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM vocabulary
        WHERE language = ?
        AND level = ?
        AND word = ?
    """, (
        language,
        level,
        word
    )).fetchone()

    conn.close()

    return row


def get_unseen_vocabulary(
    user_id,
    language,
    level
):
    """
    Get vocabulary words that this user has not seen yet.
    """

    conn = get_connection()

    rows = conn.execute("""
        SELECT v.*
        FROM vocabulary v

        LEFT JOIN learned_words lw
            ON v.id = lw.vocabulary_id
            AND lw.user_id = ?

        WHERE v.language = ?
        AND v.level = ?
        AND lw.id IS NULL

        ORDER BY RANDOM()
    """, (
        user_id,
        language,
        level
    )).fetchall()

    conn.close()

    return rows

def mark_word_seen(
    user_id,
    vocabulary_id
):
    """
    Mark a vocabulary word as seen by a user.

    Seeing a word is NOT considered a review.

    Behavior:
    - First time seen:
        * Creates learned_words record
        * first_seen = now
        * last_reviewed = NULL
        * next_review = NULL
        * review_count = 0
        * mastery = 0

    - If already seen:
        * Do nothing
        * The existing learning progress is preserved

    This ensures that:
    1. "word" never shows the same word again.
    2. The word becomes available to "quiz".
    3. Simply viewing a word does not increase review_count.
    4. Quiz results are responsible for mastery/review scheduling.
    """

    conn = get_connection()

    existing = conn.execute("""
        SELECT id
        FROM learned_words
        WHERE user_id = ?
        AND vocabulary_id = ?
    """, (
        user_id,
        vocabulary_id
    )).fetchone()

    if not existing:

        now = datetime.now().isoformat()

        conn.execute("""
            INSERT INTO learned_words (
                user_id,
                vocabulary_id,
                first_seen,
                last_reviewed,
                next_review,
                review_count,
                mastery
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            vocabulary_id,
            now,
            None,
            None,
            0,
            0
        ))

        conn.commit()

    conn.close()

def get_learned_words(
    user_id,
    language=None,
    level=None
):
    """
    Get words learned by a user.

    Optional filters:
        language
        level
    """

    conn = get_connection()

    query = """
        SELECT
            v.*,
            lw.first_seen,
            lw.last_reviewed,
            lw.next_review,
            lw.review_count,
            lw.mastery

        FROM vocabulary v

        INNER JOIN learned_words lw
            ON v.id = lw.vocabulary_id

        WHERE lw.user_id = ?
    """

    params = [user_id]

    if language:
        query += """
            AND v.language = ?
        """
        params.append(language)

    if level:
        query += """
            AND v.level = ?
        """
        params.append(level)

    query += """
        ORDER BY lw.last_reviewed DESC
    """

    rows = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    return rows


def get_language_stats(
    user_id,
    language,
    level=None
):
    """
    Return basic learning statistics.
    """

    conn = get_connection()

    query = """
        SELECT
            COUNT(*) AS total_words,
            COALESCE(SUM(
                CASE
                    WHEN lw.mastery > 0 THEN 1
                    ELSE 0
                END
            ), 0) AS mastered_words,

            COALESCE(SUM(
                lw.review_count
            ), 0) AS total_reviews

        FROM learned_words lw

        INNER JOIN vocabulary v
            ON v.id = lw.vocabulary_id

        WHERE lw.user_id = ?
        AND v.language = ?
    """

    params = [
        user_id,
        language
    ]

    if level:
        query += """
            AND v.level = ?
        """
        params.append(level)

    row = conn.execute(
        query,
        params
    ).fetchone()

    conn.close()

    return row


def set_user_language(user_id, language):
    conn = get_connection()

    now = datetime.now().isoformat()

    existing = conn.execute("""
        SELECT user_id
        FROM language_preferences
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    if existing:
        conn.execute("""
            UPDATE language_preferences
            SET
                language = ?,
                updated_at = ?
            WHERE user_id = ?
        """, (
            language,
            now,
            user_id
        ))
    else:
        conn.execute("""
            INSERT INTO language_preferences (
                user_id,
                language,
                updated_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            language,
            now
        ))

    conn.commit()
    conn.close()


def get_user_language(user_id, default="polish"):
    conn = get_connection()

    row = conn.execute("""
        SELECT language
        FROM language_preferences
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if row:
        return row["language"]

    return default

from datetime import datetime, timedelta

def set_quiz_session(user_id, vocabulary_id):
    conn = get_connection()

    now = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO language_quiz_sessions (
            user_id,
            vocabulary_id,
            created_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            vocabulary_id = excluded.vocabulary_id,
            created_at = excluded.created_at
    """, (
        user_id,
        vocabulary_id,
        now
    ))

    conn.commit()
    conn.close()


def get_quiz_session(user_id):
    conn = get_connection()

    row = conn.execute("""
        SELECT
            qs.vocabulary_id,
            qs.created_at,
            v.*
        FROM language_quiz_sessions qs
        INNER JOIN vocabulary v
            ON v.id = qs.vocabulary_id
        WHERE qs.user_id = ?
    """, (
        user_id
    )).fetchone()

    conn.close()

    return row


def clear_quiz_session(user_id):
    conn = get_connection()

    conn.execute("""
        DELETE FROM language_quiz_sessions
        WHERE user_id = ?
    """, (
        user_id
    ))

    conn.commit()
    conn.close()
    
def get_quiz_words(
    user_id,
    language,
    level,
    limit=10
):
    """
    Get words that have already been shown to the user
    and are ready for review.
    """

    conn = get_connection()

    now = datetime.now().isoformat()

    rows = conn.execute("""
        SELECT
            v.*,
            lw.first_seen,
            lw.last_reviewed,
            lw.next_review,
            lw.review_count,
            lw.mastery
        FROM vocabulary v
        INNER JOIN learned_words lw
            ON v.id = lw.vocabulary_id
        WHERE lw.user_id = ?
        AND v.language = ?
        AND v.level = ?
        AND (
            lw.next_review IS NULL
            OR lw.next_review <= ?
        )
        AND lw.mastery < 5
        ORDER BY RANDOM()
        LIMIT ?
    """, (
        user_id,
        language,
        level,
        now,
        limit
    )).fetchall()

    conn.close()

    return rows


def update_quiz_result(
    user_id,
    vocabulary_id,
    correct
):
    """
    Update mastery and review schedule after a quiz answer.
    """

    conn = get_connection()

    row = conn.execute("""
        SELECT
            mastery,
            review_count
        FROM learned_words
        WHERE user_id = ?
        AND vocabulary_id = ?
    """, (
        user_id,
        vocabulary_id
    )).fetchone()

    if not row:
        conn.close()
        return None

    current_mastery = row["mastery"] or 0
    review_count = row["review_count"] or 0

    now = datetime.now()

    if correct:

        mastery = min(
            5,
            current_mastery + 1
        )

        review_count += 1

        # Simple spaced repetition
        intervals = {
            1: 1,     # 1 day
            2: 3,     # 3 days
            3: 7,     # 7 days
            4: 14,    # 14 days
            5: 30     # 30 days
        }

        days = intervals[mastery]

        next_review = (
            now + timedelta(days=days)
        ).isoformat()

    else:

        # Wrong answer lowers mastery
        mastery = max(
            0,
            current_mastery - 1
        )

        review_count += 1

        # Review again soon
        next_review = (
            now + timedelta(minutes=10)
        ).isoformat()

    conn.execute("""
        UPDATE learned_words
        SET
            last_reviewed = ?,
            next_review = ?,
            review_count = ?,
            mastery = ?
        WHERE user_id = ?
        AND vocabulary_id = ?
    """, (
        now.isoformat(),
        next_review,
        review_count,
        mastery,
        user_id,
        vocabulary_id
    ))

    conn.commit()
    conn.close()

    return {
        "mastery": mastery,
        "review_count": review_count,
        "next_review": next_review
    }