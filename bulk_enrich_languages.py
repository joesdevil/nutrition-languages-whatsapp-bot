import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from language_db import get_connection
from language_agent import enrich_vocabulary_word


# ============================================================
# CONFIGURATION
# ============================================================

LANGUAGES = {
    "english": "B2",
    "french": "B1",
}

# Wiktionary is rate-limiting 8 workers.
# Keep this conservative.
MAX_WORKERS = 2

# Delay before processing each word.
REQUEST_DELAY = 1.0

# Retry configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 5

print_lock = threading.Lock()


# ============================================================
# GET WORDS THAT STILL NEED ENRICHMENT
# ============================================================

def get_words_to_enrich(language, level):
    conn = get_connection()

    rows = conn.execute("""
        SELECT id, word
        FROM vocabulary
        WHERE language = ?
        AND level = ?
        AND (
            translation IS NULL
            OR definition IS NULL
            OR example_sentence IS NULL
            OR example_translation IS NULL
        )
        ORDER BY id
    """, (
        language,
        level
    )).fetchall()

    conn.close()

    return rows


# ============================================================
# ENRICH ONE WORD WITH RETRIES
# ============================================================

def enrich_one(language, level, row, index, total):

    word = row["word"]

    time.sleep(REQUEST_DELAY)

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            enrich_vocabulary_word(
                language=language,
                level=level,
                word=word
            )

            with print_lock:
                print(
                    f"[{index}/{total}] ✓ "
                    f"{word}"
                )

            return True, word, None

        except Exception as error:

            error_text = str(error)

            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if "429" in error_text:

                retry_delay = (
                    INITIAL_RETRY_DELAY
                    * (2 ** (attempt - 1))
                )

                with print_lock:
                    print(
                        f"[{index}/{total}] ⚠ "
                        f"{word} -> rate limited "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
                    print(
                        f"    Waiting {retry_delay}s..."
                    )

                time.sleep(retry_delay)

                continue

            # ------------------------------------------------
            # OTHER ERROR
            # ------------------------------------------------

            with print_lock:
                print(
                    f"[{index}/{total}] ✗ "
                    f"{word} -> {error}"
                )

            return False, word, error_text

    # --------------------------------------------------------
    # RETRIES EXHAUSTED
    # --------------------------------------------------------

    with print_lock:
        print(
            f"[{index}/{total}] ✗ "
            f"{word} -> retries exhausted"
        )

    return False, word, "retries exhausted"


# ============================================================
# ENRICH LANGUAGE
# ============================================================

def enrich_language(language, level):

    print()
    print("=" * 70)
    print(f"{language.upper()} {level}")
    print("=" * 70)

    rows = get_words_to_enrich(
        language,
        level
    )

    total = len(rows)

    print(f"Words remaining: {total}")
    print(f"Workers:        {MAX_WORKERS}")
    print()

    if not rows:
        print("Nothing to enrich.")
        return

    success = 0
    failed = 0

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = []

        for index, row in enumerate(
            rows,
            start=1
        ):
            futures.append(
                executor.submit(
                    enrich_one,
                    language,
                    level,
                    row,
                    index,
                    total
                )
            )

        for future in as_completed(futures):

            try:
                result = future.result()

                if result[0]:
                    success += 1
                else:
                    failed += 1

            except Exception as error:

                failed += 1

                with print_lock:
                    print(
                        f"Worker error: {error}"
                    )

    print()
    print("-" * 70)
    print(f"{language.upper()} finished")
    print(f"Success: {success}")
    print(f"Failed:  {failed}")
    print("-" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("LANGUAGE VOCABULARY ENRICHMENT")
    print("=" * 70)
    print()
    print(f"Workers: {MAX_WORKERS}")

    for language, level in LANGUAGES.items():

        enrich_language(
            language,
            level
        )

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()