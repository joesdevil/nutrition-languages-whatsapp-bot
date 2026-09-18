import requests
import re

TATOEBA_API = "https://api.tatoeba.org/v1/sentences"

HEADERS = {
    "User-Agent": "LanguageLearningBot/1.0"
}


def is_good_example(sentence, word):
    """
    Check whether a Tatoeba sentence is suitable
    for language learning.
    """

    if not sentence:
        return False

    text = sentence.strip()

    # Too short
    if len(text) < 8:
        return False

    # Too long
    if len(text) > 150:
        return False

    words = text.split()

    # Avoid complicated sentences
    if len(words) > 20:
        return False

    # Make sure the target word appears
    pattern = r"\b" + re.escape(word) + r"\b"

    if not re.search(pattern, text, re.IGNORECASE):
        return False

    # Avoid inappropriate examples
    bad_words = [
        "fuck",
        "shit",
        "suck",
        "sucks",
        "ssie",
        "kurwa",
        "cholera",
        "pierd",
        "jeb",
        "dupa",
    ]

    text_lower = text.lower()

    for bad_word in bad_words:
        if bad_word in text_lower:
            return False

    return True


def score_example(sentence, word, translation):
    """
    Score an example sentence.
    Higher score = better example.
    """

    if not is_good_example(sentence, word):
        return -1000

    words = sentence.split()

    score = 0

    # Prefer short sentences.
    if len(words) <= 6:
        score += 5
    elif len(words) <= 10:
        score += 3
    elif len(words) <= 15:
        score += 1

    # Prefer normal sentence endings.
    if sentence.endswith((".", "!", "?")):
        score += 1

    # Translation available.
    if translation:
        score += 10

    return score


def get_best_translation(translations):
    """
    Select the best English translation.

    Prefer direct translations over indirect ones.
    """

    if not translations:
        return None

    direct_translations = [
        item
        for item in translations
        if item.get("is_direct") is True
        and item.get("text")
    ]

    if direct_translations:
        return direct_translations[0]["text"]

    for item in translations:
        text = item.get("text")

        if text:
            return text

    return None


def get_example_sentence(
    word,
    language_code,
    translation_language="eng"
):
    """
    Find a good Tatoeba example sentence
    with a matching translation.
    """

    params = {
        "lang": language_code,
        "q": word,
        "sort": "relevance",
        "limit": 30,
        "showtrans": "matching",
        "trans:lang": translation_language
    }

    response = requests.get(
        TATOEBA_API,
        params=params,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    sentences = data.get("data", [])

    if not sentences:
        return None

    candidates = []

    for sentence in sentences:

        text = sentence.get("text")

        if not text:
            continue

        translations = sentence.get(
            "translations",
            []
        )

        translation = get_best_translation(
            translations
        )

        # We require an actual translation.
        if not translation:
            continue

        if not is_good_example(text, word):
            continue

        score = score_example(
            text,
            word,
            translation
        )

        candidates.append({
            "sentence": text,
            "language": sentence.get("lang"),
            "translation": translation,
            "score": score
        })

    if not candidates:
        return None

    # Highest score first.
    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    best = candidates[0]

    return {
        "sentence": best["sentence"],
        "language": best["language"],
        "translation": best["translation"]
    }