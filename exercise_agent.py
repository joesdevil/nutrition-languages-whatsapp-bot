import os
import json
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
# from stats_db import get_connection
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free"
)

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

LABELS_FILE = Path("exercise_labels.json")


# ============================================================
# LOAD DATABASE
# ============================================================

def load_exercises():

    if not LABELS_FILE.exists():
        print("exercise_labels.json not found")
        return {}

    try:

        with open(
            LABELS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            f"Could not load exercise database: {e}"
        )

        return {}


# ============================================================
# AI INTENT DETECTION
# ============================================================

def detect_intent(message):

    message = str(message).strip()
    normalized = message.lower().strip()

    # ========================================================
    # NUMBERS
    # ========================================================

    if re.fullmatch(r"\d+", message):

        return {
            "intent": "number",
            "count": int(message),
            "exercise_name": None,
            "target": None
        }

    # ========================================================
    # GREETINGS / NORMAL CHAT
    # ========================================================

    greetings = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "thx",
        "bye",
        "goodbye"
    }

    if normalized in greetings:

        return {
            "intent": "chat",
            "count": None,
            "exercise_name": None,
            "target": None
        }

    # ========================================================
    # DIRECT WORKOUT REQUESTS
    # ========================================================

    workout_targets = {

        "push day": "push",
        "push workout": "push",

        "pull day": "pull",
        "pull workout": "pull",

        "leg day": "legs",
        "legs day": "legs",
        "leg workout": "legs",

        "upper body": "upper",
        "upper body workout": "upper",

        "lower body": "lower",
        "lower body workout": "lower",

        "full body": "full body",
        "full body workout": "full body",

        "abs workout": "abs",
        "ab workout": "abs"
    }

    if normalized in workout_targets:

        return {
            "intent": "workout",
            "count": None,
            "exercise_name": None,
            "target": workout_targets[normalized]
        }

    # ========================================================
    # TRAIN / WORK MUSCLE REQUESTS
    # ========================================================
    #
    # Examples:
    #
    # "I want to train back"
    # "I want to train chest"
    # "I want to work my legs"
    # "I want to train shoulders"
    # "train back"
    # "work chest"
    #
    # These are NOT exact exercise requests.
    # They mean the user wants exercises for a muscle.
    # ========================================================

    muscle_targets = {
        "chest": "chest",
        "back": "back",
        "shoulder": "shoulders",
        "shoulders": "shoulders",
        "biceps": "biceps",
        "triceps": "triceps",
        "arms": "arms",
        "legs": "legs",
        "leg": "legs",
        "abs": "abs",
        "abdominals": "abs",
        "glutes": "glutes",
        "hamstrings": "hamstrings",
        "quadriceps": "quadriceps",
        "quads": "quadriceps",
        "calves": "calves"
    }

    # --------------------------------------------------------
    # Remove common conversational phrases
    # --------------------------------------------------------

    cleaned = normalized

    phrases_to_remove = [
        "i want to train ",
        "i want to work ",
        "i want to workout ",
        "i want to train my ",
        "i want to work my ",
        "i want to workout my ",
        "i want to exercise ",
        "i want exercises for ",
        "give me exercises for ",
        "show me exercises for ",
        "train my ",
        "train ",
        "work my ",
        "work ",
        "workout my ",
        "workout ",
        "exercises for ",
        "exercise for "
    ]

    for phrase in phrases_to_remove:

        if cleaned.startswith(phrase):

            cleaned = cleaned[len(phrase):].strip()
            break

    # Remove question/request endings
    cleaned = re.sub(
        r"\b(muscle|muscles)\b",
        "",
        cleaned
    ).strip()

    # --------------------------------------------------------
    # Check whether the remaining text is a muscle
    # --------------------------------------------------------

    if cleaned in muscle_targets:

        return {
            "intent": "exercise_list",
            "count": None,
            "exercise_name": None,
            "target": muscle_targets[cleaned]
        }

    # ========================================================
    # OPENROUTER INTENT DETECTION
    # ========================================================

    prompt = f"""
Classify this WhatsApp fitness message.

Possible intents:

1. chat
Normal conversation, greetings, thanks, goodbye,
or unrelated conversation.

2. exact_exercise
The user is asking for ONE specific exercise.

3. exercise_list
The user wants exercises for a muscle, body part,
equipment, or category.

4. workout
The user asks for a workout such as push day,
pull day, leg day, upper body, lower body,
full body, or abs workout.

5. number
The user is providing a number after being asked
how many exercises they want.

IMPORTANT:

"hi" = chat

"hello" = chat

"crunch" = exact_exercise

"show me crunch" = exact_exercise

"seated cable row" = exact_exercise

"give me 5 chest exercises" = exercise_list

"give me 3 back exercises" = exercise_list

"I want to train back" = exercise_list

"I want to train chest" = exercise_list

"I want to work my shoulders" = exercise_list

"train legs" = exercise_list

"work my arms" = exercise_list

"push day" = workout

"pull day" = workout

"leg day" = workout

"5" = number

For exercise_list:

- count should be the requested number if provided.
- If no number is provided, count MUST be null.
- target should be the requested muscle/body part.
- Do NOT convert a muscle request into exact_exercise.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "intent": "chat",
    "count": null,
    "exercise_name": null,
    "target": null
}}

Example:

Message:
"I want to train back"

{{
    "intent": "exercise_list",
    "count": null,
    "exercise_name": null,
    "target": "back"
}}

Message:
"I want to train chest"

{{
    "intent": "exercise_list",
    "count": null,
    "exercise_name": null,
    "target": "chest"
}}

Message:
"give me 5 back exercises"

{{
    "intent": "exercise_list",
    "count": 5,
    "exercise_name": null,
    "target": "back"
}}

Message:
"crunch"

{{
    "intent": "exact_exercise",
    "count": 1,
    "exercise_name": "Crunch",
    "target": "abs"
}}

Message:
"push day"

{{
    "intent": "workout",
    "count": null,
    "exercise_name": null,
    "target": "push"
}}

Message:
"5"

{{
    "intent": "number",
    "count": 5,
    "exercise_name": null,
    "target": null
}}

User message:
{message}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify WhatsApp fitness messages. "
                    "Return ONLY valid JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0
    }

    try:

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        content = data["choices"][0]["message"]["content"].strip()

        # Remove markdown fences
        if content.startswith("```json"):
            content = content[7:]

        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        result = json.loads(content)

        return {
            "intent": result.get("intent", "chat"),
            "count": result.get("count"),
            "exercise_name": result.get("exercise_name"),
            "target": result.get("target")
        }

    except Exception as e:

        print(f"Intent detection error: {e}")

        return {
            "intent": "chat",
            "count": None,
            "exercise_name": None,
            "target": None
        }

# ============================================================
# NORMALIZE
# ============================================================

def normalize(text):

    if not text:
        return ""

    return (
        str(text)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


# # ============================================================
# # GET TRAINED EXERCISE FILENAMES
# # ============================================================


# ============================================================
# FIND EXACT EXERCISE
# ============================================================

def find_exact_exercise(
    exercise_name,
    exclude_filenames=None
):

    database = load_exercises()

    query = normalize(
        exercise_name
    )

    if not query:
        return None

    # --------------------------------------------------------
    # Previously trained filenames
    # --------------------------------------------------------

    if exclude_filenames is None:

        exclude_filenames = set()

    else:

        exclude_filenames = {
            str(filename).strip().lower()
            for filename in exclude_filenames
        }

    # ========================================================
    # 1. EXACT EXERCISE NAME
    # ========================================================

    for filename, exercise in database.items():

        filename_key = str(
            filename
        ).strip().lower()

        if filename_key in exclude_filenames:
            continue

        name = normalize(
            exercise.get(
                "exercise_name",
                ""
            )
        )

        if name == query:

            return {
                "filename": filename,
                **exercise
            }

    # ========================================================
    # 2. EXACT ALIAS
    # ========================================================

    for filename, exercise in database.items():

        filename_key = str(
            filename
        ).strip().lower()

        if filename_key in exclude_filenames:
            continue

        aliases = [

            normalize(x)

            for x in exercise.get(
                "aliases",
                []
            )

        ]

        if query in aliases:

            return {
                "filename": filename,
                **exercise
            }

    # ========================================================
    # 3. PARTIAL MATCH
    # ========================================================

    for filename, exercise in database.items():

        filename_key = str(
            filename
        ).strip().lower()

        if filename_key in exclude_filenames:
            continue

        name = normalize(
            exercise.get(
                "exercise_name",
                ""
            )
        )

        if query in name or name in query:

            return {
                "filename": filename,
                **exercise
            }

    return None


# ============================================================
# FIND MULTIPLE EXERCISES
# ============================================================

def find_exercises(
    target=None,
    count=1,
    equipment=None,
    workout_type=None,
    exclude_filenames=None
):

    database = load_exercises()

    if exclude_filenames is None:
        exclude_filenames = set()
    else:
        exclude_filenames = {
            str(filename).strip().lower()
            for filename in exclude_filenames
        }

    target = normalize(target)

    equipment = normalize(
        equipment
    )

    workout_type = normalize(
        workout_type
    )

    # --------------------------------------------------------
    # VALIDATE COUNT
    # --------------------------------------------------------

    try:

        count = int(count)

    except (TypeError, ValueError):

        count = 1

    if count <= 0:

        return []

    candidates = []

    # ========================================================
    # LOOP THROUGH DATABASE
    # ========================================================

    for filename, exercise in database.items():
        filename_key = str(
            filename
        ).strip().lower()

        if filename_key in exclude_filenames:
            continue

        name = normalize(
            exercise.get(
                "exercise_name",
                ""
            )
        )

        aliases = [

            normalize(x)

            for x in exercise.get(
                "aliases",
                []
            )

        ]

        primary = [

            normalize(x)

            for x in exercise.get(
                "primary_muscles",
                []
            )

        ]

        secondary = [

            normalize(x)

            for x in exercise.get(
                "secondary_muscles",
                []
            )

        ]

        equipment_value = normalize(
            exercise.get(
                "equipment",
                ""
            )
        )

        exercise_type = normalize(
            exercise.get(
                "exercise_type",
                ""
            )
        )

        score = 0

        # ====================================================
        # TARGET
        # ====================================================

        if target:

            # ------------------------------------------------
            # PUSH
            # ------------------------------------------------

            if target == "push":

                if any(

                    x in primary + secondary

                    for x in [
                        "chest",
                        "pectorals",
                        "pectoralis",
                        "deltoids",
                        "delts",
                        "triceps"
                    ]

                ):

                    score += 10

                if any(

                    x in name

                    for x in [
                        "bench press",
                        "chest press",
                        "shoulder press",
                        "overhead press",
                        "lateral raise",
                        "tricep",
                        "triceps"
                    ]

                ):

                    score += 10

            # ------------------------------------------------
            # PULL
            # ------------------------------------------------

            elif target == "pull":

                if any(

                    x in primary + secondary

                    for x in [
                        "back",
                        "latissimus dorsi",
                        "lats",
                        "rhomboids",
                        "biceps",
                        "traps"
                    ]

                ):

                    score += 10

                if any(

                    x in name

                    for x in [
                        "row",
                        "pulldown",
                        "pull down",
                        "pull up",
                        "curl"
                    ]

                ):

                    score += 10

            # ------------------------------------------------
            # LEGS
            # ------------------------------------------------

            elif target in (
                "legs",
                "leg"
            ):

                if any(

                    x in primary + secondary

                    for x in [
                        "quadriceps",
                        "quads",
                        "hamstrings",
                        "glutes",
                        "calves"
                    ]

                ):

                    score += 10

                if any(

                    x in name

                    for x in [
                        "squat",
                        "leg press",
                        "lunge",
                        "deadlift",
                        "calf raise",
                        "leg curl",
                        "leg extension"
                    ]

                ):

                    score += 10

            # ------------------------------------------------
            # UPPER BODY
            # ------------------------------------------------

            elif target == "upper":

                upper_muscles = [

                    "chest",
                    "pectorals",
                    "pectoralis",
                    "back",
                    "latissimus dorsi",
                    "lats",
                    "rhomboids",
                    "deltoids",
                    "delts",
                    "biceps",
                    "triceps",
                    "traps"

                ]

                if any(

                    x in primary + secondary

                    for x in upper_muscles

                ):

                    score += 10

            # ------------------------------------------------
            # LOWER BODY
            # ------------------------------------------------

            elif target == "lower":

                lower_muscles = [

                    "quadriceps",
                    "quads",
                    "hamstrings",
                    "glutes",
                    "calves"

                ]

                if any(

                    x in primary + secondary

                    for x in lower_muscles

                ):

                    score += 10

            # ------------------------------------------------
            # FULL BODY
            # ------------------------------------------------

            elif target == "full body":

                full_body_muscles = [

                    "chest",
                    "back",
                    "legs",
                    "quadriceps",
                    "hamstrings",
                    "glutes",
                    "shoulders",
                    "deltoids"

                ]

                if any(

                    x in primary + secondary

                    for x in full_body_muscles

                ):

                    score += 5

            # ------------------------------------------------
            # NORMAL MUSCLE
            # ------------------------------------------------

            else:

                if target in name:

                    score += 10

                if target in aliases:

                    score += 10

                if target in primary:

                    score += 20

                if target in secondary:

                    score += 5

                mappings = {

                    "chest": [
                        "pectorals",
                        "pectoralis",
                        "pecs"
                    ],

                    "abs": [
                        "abdominals",
                        "rectus abdominis",
                        "core",
                        "obliques"
                    ],

                    "back": [
                        "latissimus dorsi",
                        "lats",
                        "rhomboids",
                        "traps"
                    ],

                    "shoulders": [
                        "deltoids",
                        "delts"
                    ],

                    "arms": [
                        "biceps",
                        "triceps"
                    ],

                    "legs": [
                        "quadriceps",
                        "quads",
                        "hamstrings",
                        "glutes",
                        "calves"
                    ]

                }

                for muscle in mappings.get(
                    target,
                    []
                ):

                    if muscle in primary:

                        score += 15

                    if muscle in secondary:

                        score += 5

        else:

            score = 1

        # ====================================================
        # EQUIPMENT
        # ====================================================

        if equipment:

            if equipment in equipment_value:

                score += 10

            else:

                continue

        # ====================================================
        # EXERCISE TYPE
        # ====================================================

        if workout_type:

            if workout_type in exercise_type:

                score += 5

            else:

                continue

        # ====================================================
        # ADD CANDIDATE
        # ====================================================

        if score > 0:

            candidates.append(
                {
                    "filename": filename,
                    "score": score,
                    **exercise
                }
            )

    # ========================================================
    # SORT BY SCORE
    # ========================================================

    candidates.sort(

        key=lambda x: (
            x["score"],
            x.get(
                "confidence",
                0
            )
        ),

        reverse=True
    )

    
    # ========================================================
    # REMOVE DUPLICATE EXERCISES
    # ========================================================

    unique = []

    seen_names = set()
    seen_files = set()

    for exercise in candidates:

        # ----------------------------------------------------
        # Exercise name
        # ----------------------------------------------------

        name = normalize(
            exercise.get(
                "exercise_name",
                ""
            )
        )

        if not name:
            continue

        # ----------------------------------------------------
        # Filename
        # ----------------------------------------------------

        filename = str(
            exercise.get(
                "filename",
                ""
            )
        ).strip().lower()

        # ----------------------------------------------------
        # Skip duplicate exercise name
        # ----------------------------------------------------

        if name in seen_names:
            continue

        # ----------------------------------------------------
        # Skip duplicate image
        # ----------------------------------------------------

        if filename and filename in seen_files:
            continue

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        seen_names.add(name)

        if filename:
            seen_files.add(filename)

        unique.append(exercise)

        # ----------------------------------------------------
        # Stop when we have enough
        # ----------------------------------------------------

        if len(unique) >= count:
            break

    return unique
