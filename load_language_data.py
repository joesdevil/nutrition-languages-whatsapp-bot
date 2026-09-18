from cefr_words import load_words
from language_db import save_vocabulary


LANGUAGES = [
    "english",
    "french",
]


def load_language_into_database(language):
    words = load_words(language)

    if not words:
        print(f"❌ No words found for {language}")
        return 0

    count = 0

    for item in words:
        word = item.get("word")
        level = item.get("level")

        if not word or not level:
            continue

        save_vocabulary(
            language=language,
            level=level,
            word=word,
            source="local_cefr"
        )

        count += 1

    return count


def main():
    print()
    print("=" * 60)
    print("LOADING CEFR VOCABULARY INTO SQLITE")
    print("=" * 60)
    print()

    total = 0

    for language in LANGUAGES:
        print(f"Loading {language}...")

        count = load_language_into_database(language)

        print(f"  Added/updated: {count}")
        print()

        total += count

    print("=" * 60)
    print(f"DONE - {total} words processed")
    print("=" * 60)


if __name__ == "__main__":
    main()