import csv
import json
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

ENGLISH_LEVEL = "B2"
FRENCH_LEVEL = "B1"

DATA_DIR = Path("language_data")
DOWNLOAD_DIR = Path("dataset_downloads")

DATA_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True)


CEFRJ_URL = (
    "https://raw.githubusercontent.com/"
    "openlanguageprofiles/olp-en-cefrj/"
    "master/cefrj-vocabulary-profile-1.5.csv"
)

FLELEX_URL = (
    "https://cental.uclouvain.be/cefrlex/"
    "flelex/download/FleLex_TT_Beacco.tsv"
)

ENGLISH_CSV = DOWNLOAD_DIR / "cefrj-vocabulary-profile-1.5.csv"
FRENCH_TSV = DOWNLOAD_DIR / "FleLex_TT_Beacco.tsv"

ENGLISH_JSON = DATA_DIR / "english.json"
FRENCH_JSON = DATA_DIR / "french.json"


# ============================================================
# DOWNLOAD
# ============================================================

def download_file(url, destination):
    print(f"Downloading:")
    print(url)

    response = requests.get(
        url,
        timeout=30
    )

    response.raise_for_status()

    destination.write_bytes(response.content)

    print(f"Saved: {destination}")
    print()


def ensure_downloads():
    if not ENGLISH_CSV.exists():
        download_file(
            CEFRJ_URL,
            ENGLISH_CSV
        )
    else:
        print(f"Using existing: {ENGLISH_CSV}")

    if not FRENCH_TSV.exists():
        download_file(
            FLELEX_URL,
            FRENCH_TSV
        )
    else:
        print(f"Using existing: {FRENCH_TSV}")

    print()


# ============================================================
# ENGLISH CEFR-J
# ============================================================

def convert_english():
    print("=" * 60)
    print("ENGLISH CEFR-J")
    print("=" * 60)

    with open(
        ENGLISH_CSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        print("Detected columns:")
        print(reader.fieldnames)
        print()

        if not reader.fieldnames:
            raise RuntimeError(
                "Could not read English CSV header."
            )

        required_columns = {
            "headword",
            "CEFR"
        }

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise RuntimeError(
                f"Missing English columns: {missing}"
            )

        words = []

        for row in reader:
            word = (row.get("headword") or "").strip()
            level = (row.get("CEFR") or "").strip().upper()

            if not word:
                continue

            if level != ENGLISH_LEVEL:
                continue

            words.append({
                "word": word,
                "level": level
            })

    # Remove duplicates while preserving order
    unique_words = []
    seen = set()

    for item in words:
        key = item["word"].lower()

        if key in seen:
            continue

        seen.add(key)
        unique_words.append(item)

    with open(
        ENGLISH_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            unique_words,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"Target level: {ENGLISH_LEVEL}")
    print(f"Words:        {len(unique_words)}")
    print(f"Created:      {ENGLISH_JSON}")
    print()

    print("First 10 English words:")

    for item in unique_words[:10]:
        print(
            f"  {item['word']} -> {item['level']}"
        )

    print()


# ============================================================
# FRENCH FLELEX
# ============================================================

def convert_french():
    print("=" * 60)
    print("FRENCH FLELEX")
    print("=" * 60)

    with open(
        FRENCH_TSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file,
            delimiter="\t"
        )

        print("Detected columns:")
        print(reader.fieldnames)
        print()

        if not reader.fieldnames:
            raise RuntimeError(
                "Could not read French TSV header."
            )

        required_columns = {
            "word",
            "level"
        }

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise RuntimeError(
                f"Missing French columns: {missing}"
            )

        words = []

        for row in reader:
            word = (row.get("word") or "").strip()
            level = (row.get("level") or "").strip().upper()

            if not word:
                continue

            # FLELex already provides a derived CEFR level.
            if level != FRENCH_LEVEL:
                continue

            words.append({
                "word": word,
                "level": level
            })

    # Remove duplicates
    unique_words = []
    seen = set()

    for item in words:
        key = item["word"].lower()

        if key in seen:
            continue

        seen.add(key)
        unique_words.append(item)

    with open(
        FRENCH_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            unique_words,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"Target level: {FRENCH_LEVEL}")
    print(f"Words:        {len(unique_words)}")
    print(f"Created:      {FRENCH_JSON}")
    print()

    print("First 10 French words:")

    for item in unique_words[:10]:
        print(
            f"  {item['word']} -> {item['level']}"
        )

    print()


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 60)
    print("CEFR VOCABULARY CONVERTER")
    print("=" * 60)
    print()
    print(f"English target: {ENGLISH_LEVEL}")
    print(f"French target:  {FRENCH_LEVEL}")
    print()

    ensure_downloads()

    convert_english()
    convert_french()

    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()