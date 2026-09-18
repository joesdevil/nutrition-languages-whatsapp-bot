import os

from dotenv import load_dotenv
from tts_service import (
    generate_pronunciation_audio,
    generate_example_audio
)
from language_db import (
    init_language_tables,
    save_vocabulary,
    get_unseen_vocabulary,
    mark_word_seen,
    get_vocabulary,
    get_quiz_words,
    update_quiz_result,
    set_quiz_session,
    get_quiz_session,
    clear_quiz_session
)

from cefr_words import (
    get_words_for_level
)

from language_api import get_word_data
from language_parser import parse_wiktionary_data
from tatoeba_api import get_example_sentence


load_dotenv()


# --------------------------------------------------
# LANGUAGE CONFIGURATION
# --------------------------------------------------

LANGUAGE_LEVELS = {
    "english": os.getenv(
        "ENGLISH_LEVEL",
        "B1"
    ).strip().upper(),

    "french": os.getenv(
        "FRENCH_LEVEL",
        "B1"
    ).strip().upper(),

    "polish": os.getenv(
        "POLISH_LEVEL",
        "B1"
    ).strip().upper()
}


# --------------------------------------------------
# LANGUAGE CODES
# --------------------------------------------------

LANGUAGE_CODES = {
    "polish": "pol",
    "english": "eng",
    "french": "fra"
}


# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------

init_language_tables()



###################################################
def start_quiz(user_id, language):
    language = language.lower().strip()

    level = get_language_level(language)

    words = get_quiz_words(
        user_id=user_id,
        language=language,
        level=level,
        limit=1
    )

    if not words:
        return None

    word = words[0]

    set_quiz_session(
        user_id=user_id,
        vocabulary_id=word["id"]
    )

    return {
        "id": word["id"],
        "word": word["word"],
        "translation": word["translation"],
        "definition": word["definition"],
        "language": language,
        "level": word["level"],
        "mastery": word["mastery"]
    }


def answer_quiz(user_id, answer):
    session = get_quiz_session(user_id)

    if not session:
        return None

    expected = session["translation"]

    if not expected:
        return None

    answer = answer.strip().lower()
    expected = expected.strip().lower()

    correct = answer == expected

    result = update_quiz_result(
        user_id=user_id,
        vocabulary_id=session["vocabulary_id"],
        correct=correct
    )

    clear_quiz_session(user_id)

    return {
        "correct": correct,
        "word": session["word"],
        "expected": session["translation"],
        "mastery": result["mastery"],
        "review_count": result["review_count"]
    }
    
# --------------------------------------------------
# BASIC LANGUAGE FUNCTIONS
# --------------------------------------------------

def get_language_level(language):
    """
    Get configured CEFR level for a language.
    """

    language = language.lower().strip()

    return LANGUAGE_LEVELS.get(
        language,
        "B1"
    )


def get_supported_languages():
    """
    Return supported languages.
    """

    return list(
        LANGUAGE_LEVELS.keys()
    )


def get_words_for_user_level(language):
    """
    Return local CEFR words for the configured
    user level.
    """

    language = language.lower().strip()

    level = get_language_level(
        language
    )

    return get_words_for_level(
        language,
        level
    )


# --------------------------------------------------
# ENRICH ONE WORD
# --------------------------------------------------

def enrich_vocabulary_word(
    language,
    level,
    word
):
    language = language.lower().strip()
    level = level.upper().strip()
    word = word.strip()

    # --------------------------------------------------------
    # Wiktionary
    # --------------------------------------------------------

    word_data = get_word_data(
        word
    )

    parsed_data = {}

    if word_data:
        parsed_data = parse_wiktionary_data(
            word,
            word_data["wikitext"],
            language
        )

    # --------------------------------------------------------
    # Word-level translation
    # --------------------------------------------------------

    translation = parsed_data.get(
        "translation"
    )

    # --------------------------------------------------------
    # Tatoeba example
    # --------------------------------------------------------

    language_code = LANGUAGE_CODES.get(
        language
    )

    example = None

    if language_code:

        try:

            example = get_example_sentence(
                word,
                language_code
            )

        except Exception as error:

            print(
                f"Tatoeba error for "
                f"{word}: {error}"
            )

            example = None

    example_sentence = None
    example_translation = None

    if example:

        example_sentence = (
            example.get("sentence")
        )

        example_translation = (
            example.get("translation")
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    vocabulary_id = save_vocabulary(
        language=language,
        level=level,
        word=word,

        # IMPORTANT:
        # This is now the WORD translation,
        # not the Tatoeba sentence translation.
        translation=translation,

        definition=parsed_data.get(
            "definition"
        ),

        part_of_speech=parsed_data.get(
            "part_of_speech"
        ),

        pronunciation=parsed_data.get(
            "pronunciation"
        ),

        example_sentence=example_sentence,

        example_translation=example_translation,

        source="local_cefr",

        source_id=None
    )

    return vocabulary_id


# --------------------------------------------------
# DAILY WORD
# --------------------------------------------------

def get_daily_word(
    language,
    user_id
):
    """
    Get a new vocabulary word for the user.

    Flow:

        1. Read configured CEFR level.
        2. Find unseen local CEFR word.
        3. Enrich it using Wiktionary.
        4. Enrich it using Tatoeba.
        5. Save everything to SQLite.
        6. Mark word as seen.
        7. Return complete vocabulary data.
    """

    language = language.lower().strip()

    level = get_language_level(
        language
    )

    # --------------------------------------------------
    # Find unseen word
    # --------------------------------------------------

    unseen_words = get_unseen_vocabulary(
        user_id=user_id,
        language=language,
        level=level
    )

    # --------------------------------------------------
    # No more words
    # --------------------------------------------------

    if not unseen_words:

        # Check whether the CEFR source actually
        # contains words for this language/level.

        local_words = get_words_for_level(
            language,
            level
        )

        if not local_words:
            return None

        return None

    # --------------------------------------------------
    # Select word
    # --------------------------------------------------

    word_row = unseen_words[0]

    word = word_row["word"]

    vocabulary_id = word_row["id"]

    # --------------------------------------------------
    # Enrich word
    # --------------------------------------------------

    enrich_vocabulary_word(
        language=language,
        level=level,
        word=word
    )

    # --------------------------------------------------
    # Get the updated vocabulary row
    #
    # We query again because enrichment may have
    # updated the existing database row.
    # --------------------------------------------------

    from language_db import get_vocabulary

    vocabulary = get_vocabulary(
        language=language,
        level=level,
        word=word
    )

    if not vocabulary:
        return None

    vocabulary_id = vocabulary["id"]

    # --------------------------------------------------
    # Mark as seen
    # --------------------------------------------------

    mark_word_seen(
        user_id=user_id,
        vocabulary_id=vocabulary_id
    )

    # --------------------------------------------------
    # Return complete word
    # --------------------------------------------------
    word_audio_path = None
    example_audio_path = None


    # ============================================================
    # WORD AUDIO
    # ============================================================

    try:

        word_audio_path = generate_pronunciation_audio(
            text=vocabulary["word"],
            language=language,
            vocabulary_id=vocabulary["id"]
        )

    except Exception as error:

        print(
            f"TTS word error for "
            f"{vocabulary['word']}: {error}"
        )


    # ============================================================
    # EXAMPLE SENTENCE AUDIO
    # ============================================================

    if vocabulary["example_sentence"]:

        try:

            example_audio_path = generate_example_audio(
                text=vocabulary["example_sentence"],
                language=language,
                vocabulary_id=vocabulary["id"]
            )

        except Exception as error:

            print(
                f"TTS example error for "
                f"{vocabulary['word']}: {error}"
            )


    return {
        "word": vocabulary["word"],
        "level": vocabulary["level"],
        "translation": vocabulary["translation"],
        "part_of_speech": vocabulary["part_of_speech"],
        "pronunciation": vocabulary["pronunciation"],
        "definition": vocabulary["definition"],
        "example_sentence": vocabulary["example_sentence"],
        "example_translation": vocabulary["example_translation"],

        "audio_path": (
            str(word_audio_path)
            if word_audio_path
            else None
        ),

        "example_audio_path": (
            str(example_audio_path)
            if example_audio_path
            else None
        )
    }