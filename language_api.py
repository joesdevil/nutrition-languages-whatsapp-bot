import requests


WIKTIONARY_API = (
    "https://en.wiktionary.org/w/api.php"
)

HEADERS = {
    "User-Agent": (
        "LanguageLearningBot/1.0 "
        "(language-learning-project)"
    )
}


def get_word_data(word):
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json"
    }

    response = requests.get(
        WIKTIONARY_API,
        params=params,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        return None

    parse_data = data.get("parse")

    if not parse_data:
        return None

    wikitext = (
        parse_data
        .get("wikitext", {})
        .get("*", "")
    )

    if not wikitext:
        return None

    return {
        "word": word,
        "wikitext": wikitext
    }