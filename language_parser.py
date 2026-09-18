import re


def clean_wikitext(text):
    if not text:
        return ""

    text = re.sub(
        r"\{\{[^{}]*\}\}",
        "",
        text
    )

    text = re.sub(
        r"\[\[([^|\]]+)\|([^\]]+)\]\]",
        r"\2",
        text
    )

    text = re.sub(
        r"\[\[([^\]]+)\]\]",
        r"\1",
        text
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    text = text.replace("'''", "")
    text = text.replace("''", "")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def extract_language_section(
    wikitext,
    language
):
    if not wikitext:
        return ""

    language = language.strip()

    pattern = (
        r"^=="
        + re.escape(language)
        + r"==[ \t]*$"
    )

    match = re.search(
        pattern,
        wikitext,
        re.MULTILINE | re.IGNORECASE
    )

    if not match:
        return ""

    start = match.end()

    next_heading = re.search(
        r"^==[^=].*?==[ \t]*$",
        wikitext[start:],
        re.MULTILINE
    )

    if next_heading:
        end = (
            start
            + next_heading.start()
        )

        return wikitext[
            start:end
        ].strip()

    return wikitext[start:].strip()


def extract_part_of_speech(section):
    patterns = {
        "noun": r"^===Noun===\s*$",
        "verb": r"^===Verb===\s*$",
        "adjective": r"^===Adjective===\s*$",
        "adverb": r"^===Adverb===\s*$",
        "pronoun": r"^===Pronoun===\s*$",
        "preposition": r"^===Preposition===\s*$",
        "conjunction": r"^===Conjunction===\s*$",
        "numeral": r"^===Numeral===\s*$",
        "particle": r"^===Particle===\s*$",
        "interjection": r"^===Interjection===\s*$",
    }

    for part_of_speech, pattern in patterns.items():

        if re.search(
            pattern,
            section,
            re.MULTILINE | re.IGNORECASE
        ):
            return part_of_speech

    return None


def extract_pronunciation(section):
    if not section:
        return None

    pronunciation_match = re.search(
        r"^===Pronunciation===\s*$"
        r"([\s\S]*?)"
        r"(?=^===|\Z)",
        section,
        re.MULTILINE | re.IGNORECASE
    )

    if pronunciation_match:
        pronunciation_section = (
            pronunciation_match.group(1)
        )
    else:
        pronunciation_section = section

    ipa_match = re.search(
        r"\{\{IPA\|pl\|([^|}]+)",
        pronunciation_section,
        re.IGNORECASE
    )

    if ipa_match:
        return ipa_match.group(1).strip()

    pl_pr_match = re.search(
        r"\{\{pl-pr\|([^}]*)\}\}",
        pronunciation_section,
        re.IGNORECASE
    )

    if pl_pr_match:

        template_content = (
            pl_pr_match.group(1)
        )

        mp_match = re.search(
            r"(?:^|\|)mp=([^|}]*)",
            template_content,
            re.IGNORECASE
        )

        if mp_match:

            pronunciation = (
                mp_match.group(1).strip()
            )

            pronunciation = (
                pronunciation
                .replace("#", "")
                .strip(" ,")
            )

            if pronunciation:
                return pronunciation

    return None


def extract_definition(section):
    if not section:
        return None

    for line in section.splitlines():

        line = line.strip()

        if not line.startswith("# "):
            continue

        definition = line[2:].strip()

        definition = clean_wikitext(
            definition
        )

        if definition:
            return definition

    return None


def extract_translation(section):
    """
    Extract the first English meaning from the definition.

    Example Wiktionary:

        # [[house]] {{gl|building for living}}
        # [[home]] {{gl|place where one resides}}

    Returns:

        house
    """

    if not section:
        return None

    # --------------------------------------------------------
    # Find the first definition line
    # --------------------------------------------------------

    for line in section.splitlines():

        line = line.strip()

        if not line.startswith("# "):
            continue

        # ----------------------------------------------------
        # Extract the first [[...]] link
        # ----------------------------------------------------

        match = re.search(
            r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]",
            line
        )

        if not match:
            continue

        translation = match.group(1).strip()

        # ----------------------------------------------------
        # Ignore non-translation links
        # ----------------------------------------------------

        ignored = {
            "house",
        }

        # We actually want house here, so do not ignore it.
        # This set is intentionally empty for now.

        # ----------------------------------------------------
        # Clean the result
        # ----------------------------------------------------

        translation = clean_wikitext(
            translation
        )

        if translation:
            return translation

    return None



def parse_wiktionary_data(
    word,
    wikitext,
    language="polish"
):
    result = {
        "word": word,
        "language": language,
        "part_of_speech": None,
        "definition": None,
        "translation": None,
        "pronunciation": None
    }

    if not wikitext:
        return result

    language_names = {
        "polish": "Polish",
        "english": "English",
        "french": "French"
    }

    language_name = language_names.get(
        language.lower(),
        language
    )

    section = extract_language_section(
        wikitext,
        language_name
    )

    if not section:
        return result

    result["part_of_speech"] = (
        extract_part_of_speech(
            section
        )
    )

    result["definition"] = (
        extract_definition(
            section
        )
    )

    result["translation"] = (
        extract_translation(
            section
        )
    )

    result["pronunciation"] = (
        extract_pronunciation(
            section
        )
    )

    return result