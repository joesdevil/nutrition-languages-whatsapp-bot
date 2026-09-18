from tts_service import generate_pronunciation_audio


tests = [
    ("bête", "french"),
    ("beast", "english"),
    ("dzień", "polish"),
]


for text, language in tests:

    audio = generate_pronunciation_audio(
        text=text,
        language=language
    )

    print(
        f"{language}: {text}"
    )

    print(
        f"Generated: {audio}"
    )