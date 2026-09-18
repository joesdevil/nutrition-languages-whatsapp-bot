import json
import random as random_module
from pathlib import Path


DATA_DIR = Path("language_data")


def load_words(language):

    file_path = DATA_DIR / f"{language.lower()}.json"

    if not file_path.exists():
        return []

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def get_words_for_level(
    language,
    level
):

    words = load_words(language)

    level = level.upper()

    return [
        word
        for word in words
        if word.get("level") == level
    ]


def get_random_word_for_level(
    language,
    level
):

    words = get_words_for_level(
        language,
        level
    )

    if not words:
        return None

    return random_module.choice(words)