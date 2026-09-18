import asyncio
from pathlib import Path
import edge_tts


# ============================================================
# CONFIGURATION
# ============================================================

AUDIO_DIR = Path("language_audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# VOICES
# ============================================================

LANGUAGE_VOICES = {
    "french": "fr-FR-DeniseNeural",
    "english": "en-US-JennyNeural",
    "polish": "pl-PL-ZofiaNeural",
}


# ============================================================
# GENERATE AUDIO
# ============================================================

async def _generate_audio(text, voice, output_path):

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice
    )

    await communicate.save(
        str(output_path)
    )


def generate_audio(
    text,
    language,
    filename
):
    """
    Generate an MP3 file for the given text.
    """

    if not text:
        return None

    language = language.lower().strip()

    voice = LANGUAGE_VOICES.get(language)

    if not voice:
        raise ValueError(
            f"Unsupported TTS language: {language}"
        )

    output_path = AUDIO_DIR / filename

    # Do not regenerate existing audio
    if output_path.exists():
        return output_path

    asyncio.run(
        _generate_audio(
            text=text,
            voice=voice,
            output_path=output_path
        )
    )

    return output_path


# ============================================================
# WORD PRONUNCIATION
# ============================================================

def generate_pronunciation_audio(
    text,
    language,
    vocabulary_id
):
    """
    Generate pronunciation audio for a vocabulary word.
    """

    filename = (
        f"{language}_{vocabulary_id}_word.mp3"
    )

    return generate_audio(
        text=text,
        language=language,
        filename=filename
    )


# ============================================================
# EXAMPLE SENTENCE PRONUNCIATION
# ============================================================

def generate_example_audio(
    text,
    language,
    vocabulary_id
):
    """
    Generate pronunciation audio for the example sentence.
    """

    filename = (
        f"{language}_{vocabulary_id}_example.mp3"
    )

    return generate_audio(
        text=text,
        language=language,
        filename=filename
    )
    
# ============================================================
# CONFIGURATION
# ============================================================

AUDIO_DIR = Path("language_audio")

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# VOICES
# ============================================================

LANGUAGE_VOICES = {
    "french": "fr-FR-DeniseNeural",
    "english": "en-US-JennyNeural",
    "polish": "pl-PL-ZofiaNeural",
}


# ============================================================
# LANGUAGE CODES
# ============================================================

LANGUAGE_CODES = {
    "french": "fr",
    "english": "en",
    "polish": "pl",
}





# ============================================================
# GENERATE SENTENCE AUDIO
# ============================================================

def generate_sentence_audio(
    text,
    language,
    filename=None
):
    """
    Generate pronunciation audio for a complete sentence.
    """

    if not text:
        return None

    language = language.lower().strip()

    voice = LANGUAGE_VOICES.get(language)

    if not voice:
        raise ValueError(
            f"Unsupported TTS language: {language}"
        )

    if filename is None:

        safe_text = "".join(
            char if char.isalnum() else "_"
            for char in text
        )

        filename = f"{language}_sentence_{safe_text}.mp3"

    output_path = AUDIO_DIR / filename

    if output_path.exists():
        return output_path

    asyncio.run(
        _generate_audio(
            text=text,
            voice=voice,
            output_path=output_path
        )
    )

    return output_path
