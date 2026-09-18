from cefr_words import load_words
from language_db import save_vocabulary


def load_language_into_database(language):
    words = load_words(language)

    count = 0

    for item in words:
        save_vocabulary(
            language=language,
            level=item["level"],
            word=item["word"],
            source="local_cefr"
        )

        count += 1

    return count