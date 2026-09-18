from language_db import (
    init_language_tables,
    get_vocabulary,
    get_learned_words
)

from language_agent import (
    enrich_vocabulary_word,
    get_daily_word
)


# ============================================================
# TEST 1: Initialize database
# ============================================================

print("\n" + "=" * 60)
print("TEST 1: INITIALIZE DATABASE")
print("=" * 60)

init_language_tables()

print("Database initialized successfully.")


# ============================================================
# TEST 2: Enrich existing word
# ============================================================

print("\n" + "=" * 60)
print("TEST 2: ENRICH 'dom'")
print("=" * 60)

vocabulary_id = enrich_vocabulary_word(
    language="polish",
    level="A1",
    word="dom"
)

print(f"Vocabulary ID: {vocabulary_id}")


# ============================================================
# TEST 3: Check enriched word
# ============================================================

print("\n" + "=" * 60)
print("TEST 3: CHECK 'dom' IN DATABASE")
print("=" * 60)

word = get_vocabulary(
    language="polish",
    level="A1",
    word="dom"
)

if word:

    print(f"ID:                 {word['id']}")
    print(f"Language:           {word['language']}")
    print(f"Level:              {word['level']}")
    print(f"Word:               {word['word']}")
    print(f"Translation:        {word['translation']}")
    print(f"Definition:         {word['definition']}")
    print(f"Part of speech:     {word['part_of_speech']}")
    print(f"Pronunciation:      {word['pronunciation']}")
    print(f"Example:            {word['example_sentence']}")
    print(f"Example translation:{word['example_translation']}")

else:

    print("ERROR: Word was not found.")


# ============================================================
# TEST 4: Daily word
# ============================================================

print("\n" + "=" * 60)
print("TEST 4: GET DAILY WORD")
print("=" * 60)

user_id = "test-user"

daily_word = get_daily_word(
    language="polish",
    user_id=user_id
)

if daily_word:

    print(f"Word:               {daily_word['word']}")
    print(f"Level:              {daily_word['level']}")
    print(f"Translation:        {daily_word['translation']}")
    print(f"Definition:         {daily_word['definition']}")
    print(f"Part of speech:     {daily_word['part_of_speech']}")
    print(f"Pronunciation:      {daily_word['pronunciation']}")
    print(f"Example:            {daily_word['example_sentence']}")
    print(f"Example translation:{daily_word['example_translation']}")

else:

    print("No unseen Polish A1 words available.")


# ============================================================
# TEST 5: Check learned words
# ============================================================

print("\n" + "=" * 60)
print("TEST 5: LEARNED WORDS")
print("=" * 60)

learned_words = get_learned_words(
    user_id=user_id,
    language="polish",
    level="A1"
)

if learned_words:

    for item in learned_words:

        print(
            f"{item['word']} | "
            f"review_count={item['review_count']} | "
            f"mastery={item['mastery']}"
        )

else:

    print("No learned words found.")


# ============================================================
# FINISHED
# ============================================================

print("\n" + "=" * 60)
print("ALL TESTS FINISHED")
print("=" * 60)
