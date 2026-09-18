import time

from language_db import (
    get_connection,
    get_vocabulary
)

from language_agent import (
    enrich_vocabulary_word
)


LANGUAGE = "polish"
LEVEL = "A1"

DELAY_SECONDS = 2


def get_words_to_enrich():
    conn = get_connection()

    rows = conn.execute("""
        SELECT id, word
        FROM vocabulary
        WHERE language = ?
        AND level = ?
        ORDER BY id
    """, (
        LANGUAGE,
        LEVEL
    )).fetchall()

    conn.close()

    return rows


def main():

    print()
    print("=" * 60)
    print("POLISH A1 BULK ENRICHMENT")
    print("=" * 60)

    words = get_words_to_enrich()

    print(f"Words found: {len(words)}")
    print()

    success = 0
    failed = 0

    for index, row in enumerate(words, start=1):

        word = row["word"]

        print(
            f"[{index}/{len(words)}] "
            f"Enriching: {word}"
        )

        try:

            vocabulary_id = enrich_vocabulary_word(
                language=LANGUAGE,
                level=LEVEL,
                word=word
            )

            vocabulary = get_vocabulary(
                language=LANGUAGE,
                level=LEVEL,
                word=word
            )

            if vocabulary:

                print(
                    f"    Translation: "
                    f"{vocabulary['translation']}"
                )

                print(
                    f"    Definition: "
                    f"{vocabulary['definition']}"
                )

                print(
                    f"    Part of speech: "
                    f"{vocabulary['part_of_speech']}"
                )

                print(
                    f"    Pronunciation: "
                    f"{vocabulary['pronunciation']}"
                )

                print(
                    f"    Example: "
                    f"{vocabulary['example_sentence']}"
                )

                print(
                    f"    Example translation: "
                    f"{vocabulary['example_translation']}"
                )

                success += 1

            else:

                print(
                    "    ERROR: "
                    "Word not found after enrichment."
                )

                failed += 1

        except Exception as error:

            print(
                f"    ERROR: {error}"
            )

            failed += 1

        print()

        if index < len(words):

            print(
                f"    Waiting "
                f"{DELAY_SECONDS} seconds..."
            )

            time.sleep(
                DELAY_SECONDS
            )

            print()

    print("=" * 60)
    print("ENRICHMENT FINISHED")
    print("=" * 60)

    print(
        f"Successful: {success}"
    )

    print(
        f"Failed:     {failed}"
    )

    print(
        f"Total:      {len(words)}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()