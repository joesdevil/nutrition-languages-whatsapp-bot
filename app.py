from flask import Flask, request, Response, send_from_directory
import requests
import os
import re
import json
from tts_service import generate_pronunciation_audio
from tts_service import generate_audio
from datetime import datetime, timedelta
from usda_api import search_food, calculate_nutrition
from language_scenarios import (
    get_scenario,
    get_random_scenario,
    get_scenario_names
)
from stats_db import (
    init_db,
    create_meal,
    add_meal_item,
    get_daily_nutrition,
    start_pending_workout,
    add_pending_exercise,
    get_pending_workout,
    complete_pending_workout,
    get_stats,
    get_exercises_by_date,
    get_nutrition_by_date,
    get_exercises_by_period,
    get_muscle_stats,
    get_trained_exercise_filenames,
    get_pending_exercise,
    add_exercise_set,
    set_exercise_sets_count,
    get_pending_exercise_sets,
    complete_pending_exercise
)

from language_agent import (
    get_daily_word,
    get_language_level,
    get_supported_languages
)

from language_db import (
    set_user_language,
    get_user_language,
    get_quiz_words,
    update_quiz_result
)

from dotenv import load_dotenv
from pathlib import Path

from exercise_agent import (
    detect_intent,
    find_exercises,
    find_exact_exercise
)

load_dotenv()

app = Flask(__name__)

init_db()

# ============================================================
# CONFIG
# ============================================================


LANGUAGE_AUDIO_DIR = Path("language_audio")

TWILIO_ACCOUNT_SID = os.getenv(
    "TWILIO_ACCOUNT_SID"
)

TWILIO_AUTH_TOKEN = os.getenv(
    "TWILIO_AUTH_TOKEN"
)
exerciseFolder = os.getenv(
    "EXERCISE_IMAGE_DIR",
    "exercise_images"
)

mp4Folder = os.getenv(
    "EXERCISE_mp4_DIR",
    "exercise_mp4s"
)


TWILIO_WHATSAPP_FROM = os.getenv(
    "TWILIO_WHATSAPP_FROM"
)

NGROK_URL = os.getenv(
    "NGROK_URL",
    ""
).rstrip("/")


# ============================================================
# PENDING WORKOUTS
#
# Example:
#
# User: Push day
# Bot: How many exercises?
# User: 5
#
# pending_workouts remembers that "5" belongs
# to the previous Push Day request.
# ============================================================

pending_workouts = {}
pending_set_tracking = {}
pending_sets = {}
pending_stats_choice = {}
pending_stats_period = {}

# Remember the most recently sent exercise for each user
last_sent_exercises = {}
# ============================================================
# LANGUAGE QUIZ SESSIONS
# ============================================================

pending_language_quiz = {}

# ============================================================
# OPENROUTER CHAT
# ============================================================

def ai_response(message):

    api_key = os.getenv(
        "OPENROUTER_API_KEY"
    )

    model = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free"
    )

    url = (
        "https://openrouter.ai/api/v1/"
        "chat/completions"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a friendly fitness and nutrition "
                    "assistant on WhatsApp. "
                    "Keep answers concise and natural. "
                    "Do not return exercise images yourself. "
                    "Exercise images are handled separately."
                )
            },
            {
                "role": "user",
                "content": message
            }
        ],

        "temperature": 0.3
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]




def parse_set_count(message):
    text = message.lower().strip()

    match = re.fullmatch(
        r"(\d{1,2})\s*sets?",
        text
    )

    if match:
        count = int(match.group(1))

        if 1 <= count <= 20:
            return count

    return None

def parse_set_data(message):
    text = message.lower().strip()

    # Example:
    # 60 10
    # 60kg 10
    # 60kg x 10
    # 60 kg × 10 reps

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilograms)?"
        r"\s*(?:x|×|\*)\s*"
        r"(\d+)\s*(?:reps?|r)?",
        text
    )

    if not match:
        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilograms)?"
            r"\s+"
            r"(\d+)\s*(?:reps?|r)?",
            text
        )

    if match:
        return {
            "weight": float(match.group(1)),
            "reps": int(match.group(2)),
            "duration_seconds": None
        }

    # reps only
    match = re.fullmatch(
        r"(\d+)\s*(?:reps?|r)",
        text
    )

    if match:
        return {
            "weight": None,
            "reps": int(match.group(1)),
            "duration_seconds": None
        }

    # duration
    match = re.fullmatch(
        r"(\d+)\s*(?:sec|secs|seconds|s)",
        text
    )

    if match:
        return {
            "weight": None,
            "reps": None,
            "duration_seconds": int(match.group(1))
        }

    return None

def handle_set_tracking(user_number, message):
    tracking = pending_set_tracking.get(user_number)

    if not tracking:
        return False

    set_data = parse_set_data(message)

    if not set_data:
        send_whatsapp_message(
            user_number,
            "❌ I couldn't understand that.\n\n"
            "Send your set like:\n"
            "• 60kg x 10\n"
            "• 60 10\n"
            "• 10 reps\n"
            "• 60 sec"
        )
        return True

    pending_exercise_id = tracking["pending_exercise_id"]
    current_set = tracking["current_set"]
    sets_count = tracking["sets_count"]

    add_exercise_set(
        pending_exercise_id=pending_exercise_id,
        set_number=current_set,
        weight=set_data["weight"],
        reps=set_data["reps"],
        duration_seconds=set_data["duration_seconds"]
    )

    if set_data["duration_seconds"] is not None:
        confirmation = (
            f"✅ Set {current_set}: "
            f"{set_data['duration_seconds']} sec"
        )
    elif set_data["weight"] is not None:
        confirmation = (
            f"✅ Set {current_set}: "
            f"{set_data['weight']} kg × "
            f"{set_data['reps']} reps"
        )
    else:
        confirmation = (
            f"✅ Set {current_set}: "
            f"{set_data['reps']} reps"
        )

    if current_set < sets_count:
        tracking["current_set"] += 1

        send_whatsapp_message(
            user_number,
            f"{confirmation}\n\n"
            f"💪 Set {tracking['current_set']} — "
            f"send weight + reps."
        )

    else:
        # complete_pending_exercise(pending_exercise_id)

        pending_set_tracking.pop(user_number, None)

        send_whatsapp_message(
            user_number,
            f"{confirmation}\n\n"
            f"🎉 {tracking['exercise_name']} completed!\n\n"
            "You can log another exercise or send *done* "
            "when you've finished your workout."
        )

    return True

def start_set_tracking(user_number, exercise_name, sets_count):
    exercise = get_pending_exercise(
        user_number,
        exercise_name
    )

    if not exercise:
        return False

    set_exercise_sets_count(
        exercise["id"],
        sets_count
    )

    pending_set_tracking[user_number] = {
        "pending_exercise_id": exercise["id"],
        "exercise_name": exercise["exercise_name"],
        "sets_count": sets_count,
        "current_set": 1
    }

    send_whatsapp_message(
        user_number,
        f"💪 {exercise['exercise_name']}\n\n"
        f"You're doing {sets_count} sets.\n\n"
        "Send Set 1 like:\n"
        "• 60kg x 10\n"
        "• 60 10\n"
        "• 10 reps"
    )

    return True


def parse_exercise_set_request(message):
    text = message.strip()

    match = re.match(
        r"^(.+?)\s+(\d{1,2})\s*sets?$",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    exercise_name = match.group(1).strip()
    sets_count = int(match.group(2))

    if not 1 <= sets_count <= 20:
        return None

    return exercise_name, sets_count

def is_meal_message(message):
    text = message.lower().strip()

    meal_phrases = [
        "i ate",
        "i had",
        "ate ",
        "had ",
        "eaten",
        "meal:"
    ]

    return any(
        phrase in text
        for phrase in meal_phrases
    )


def parse_meal_message(message):
    text = message.strip()

    # Remove the beginning of the sentence
    text = re.sub(
        r"^(?:i\s+ate|i\s+had|ate|had|meal:?)\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Find every quantity + unit in the message
    pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*(g|kg)\b",
        re.IGNORECASE
    )

    matches = list(pattern.finditer(text))

    if not matches:
        return None

    foods = []

    for index, match in enumerate(matches):

        quantity = float(match.group(1))
        unit = match.group(2).lower()

        if unit == "kg":
            quantity *= 1000

        # Food name starts after this quantity
        start = match.end()

        # Food name ends before the next quantity
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        food_name = text[start:end].strip()

        # Remove common connecting words
        food_name = re.sub(
            r"^(?:of\s+|with\s+|and\s+)+",
            "",
            food_name,
            flags=re.IGNORECASE
        )

        food_name = re.sub(
            r"\s+(?:with|and)\s*$",
            "",
            food_name,
            flags=re.IGNORECASE
        )

        if not food_name:
            continue

        foods.append({
            "food_name": food_name,
            "quantity_grams": quantity
        })

    if not foods:
        return None

    return {
        "foods": foods
    }
    

def log_meal(
    user_number,
    foods,
    meal_type=None
):
    results = []

    # Create ONE meal
    meal_id = create_meal(
        user_number,
        meal_type=meal_type
    )

    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0

    for food_data in foods:

        food_name = food_data["food_name"]
        quantity_grams = food_data["quantity_grams"]

        # Search USDA
        usda_foods = search_food(food_name)

        if not usda_foods:
            continue

        # Default to first result
        food = usda_foods[0]

        # Prefer exact match
        search_name = food_name.strip().lower()

        for candidate in usda_foods:
            description = (
                candidate.get("description") or ""
            ).strip().lower()

            if description == search_name:
                food = candidate
                break

        fdc_id = food.get("fdcId")
        description = (
            food.get("description")
            or food_name
        )

        # Calculate nutrition
        nutrition = calculate_nutrition(
            fdc_id,
            quantity_grams
        )

        # Save item
        add_meal_item(
            meal_id=meal_id,
            food_name=description,
            fdc_id=fdc_id,
            quantity=quantity_grams,
            unit="g",
            calories=nutrition["calories"],
            protein=nutrition["protein"],
            carbs=nutrition["carbs"],
            fat=nutrition["fat"]
        )

        results.append({
            "food_name": description,
            "quantity": quantity_grams,
            **nutrition
        })

        total_calories += nutrition["calories"]
        total_protein += nutrition["protein"]
        total_carbs += nutrition["carbs"]
        total_fat += nutrition["fat"]

    if not results:
        return None

    return {
        "items": results,
        "total_calories": round(total_calories, 2),
        "total_protein": round(total_protein, 2),
        "total_carbs": round(total_carbs, 2),
        "total_fat": round(total_fat, 2)
    }
# ============================================================
# SEND TEXT
# ============================================================

def send_whatsapp_message(to, message):

    url = (
        f"https://api.twilio.com/2010-04-01/"
        f"Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    )

    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": f"whatsapp:{to}",
        "Body": message
    }

    response = requests.post(
        url,
        data=data,
        auth=(
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN
        )
    )

    print(
        "WhatsApp text:",
        response.status_code
    )

    if response.status_code >= 400:
        print(response.text)


# ============================================================
# SEND IMAGE
# ============================================================

def send_whatsapp_image(
    to,
    image_url,
    caption=None
):

    url = (
        f"https://api.twilio.com/2010-04-01/"
        f"Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    )

    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": f"whatsapp:{to}",
        "MediaUrl": image_url
    }

    if caption:
        data["Body"] = caption

    response = requests.post(
        url,
        data=data,
        auth=(
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN
        )
    )

    print(
        "WhatsApp image:",
        response.status_code
    )

    if response.status_code >= 400:
        print(response.text)



def send_whatsapp_mp4(
    to,
    mp4_url,
    caption=None
):

    url = (
        f"https://api.twilio.com/2010-04-01/"
        f"Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    )

    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": f"whatsapp:{to}",
        "MediaUrl": mp4_url
    }

    if caption:
        data["Body"] = caption

    response = requests.post(
        url,
        data=data,
        auth=(
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN
        )
    )

    print(
        "WhatsApp mp4:",
        response.status_code
    )

    print(
        "Twilio response:",
        response.text
    )

    if response.status_code >= 400:
        print(response.text)
  
  
# ============================================================
# SEND AUDIO
# ============================================================

def send_whatsapp_audio(
    to,
    audio_url
):

    url = (
        f"https://api.twilio.com/2010-04-01/"
        f"Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    )

    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": f"whatsapp:{to}",
        "MediaUrl": audio_url
    }

    response = requests.post(
        url,
        data=data,
        auth=(
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN
        )
    )

    print(
        "WhatsApp audio:",
        response.status_code
    )

    print(
        "Twilio audio response:",
        response.text
    )

    if response.status_code >= 400:
        print(
            "Audio sending error:",
            response.text
        )      
# ============================================================
# BUILD IMAGE URL
# ============================================================

def get_image_url(filename):

    if not NGROK_URL:

        raise RuntimeError(
            "NGROK_URL is not configured in .env"
        )

    return (
        f"{NGROK_URL}/{exerciseFolder}/{filename}"
    )


def get_mp4_url(filename):

    if not NGROK_URL:
        raise RuntimeError(
            "NGROK_URL is not configured in .env"
        )

    base_name = os.path.splitext(filename)[0]

    mp4_filename = f"{base_name}.mp4"

    return (
        f"{NGROK_URL}/{mp4Folder}/{mp4_filename}"
    )
    
# ============================================================
# SEND EXERCISE
# ============================================================

def send_exercise(
    user_number,
    exercise
):

    filename = exercise["filename"]

    name = exercise.get(
        "exercise_name",
        "Exercise"
    )

    # Remember the last exercise sent to this user
    last_sent_exercises[user_number] = {
        "exercise_name": name,
        "filename": filename
    }

    image_url = get_image_url(
        filename
    )

    print(
        f"Sending exercise: {name}"
    )

    send_whatsapp_image(
        user_number,
        image_url,
        caption=f"💪 {name}"
    )

# ============================================================
# STATS / COMPLETION DETECTION
# ============================================================

def is_completion_message(message):

    text = message.lower().strip()

    completion_phrases = {
        "i did this",
        "i did it",
        "i did them",
        "i did all",
        "i did all of them",
        "i completed this",
        "i completed it",
        "i completed them",
        "i completed all",
        "completed",
        "complete",
        "done",
        "all done",
        "finished",
        "i finished",
        "workout completed",
        "workout complete",
        "i finished the workout",
        "i did today's workout",
        "i did todays workout",
        "i did the workout",
        "i finished today's workout",
        "i finished todays workout"
    }

    return (
        text in completion_phrases
        or any(
            text.startswith(
                phrase + " "
            )
            for phrase in completion_phrases
        )
    )

def is_stats_message(message):

    text = message.lower().strip()

    stats_phrases = {
        "stats",
        "my stats",
        "show my stats",
        "show me my stats",
        "my progress",
        "show my progress",
        "training stats",
        "workout stats",
        "what did i train",
        "what did i do",
        "what have i trained",
        "how many days did i train",
        "how many exercises did i do",

        # Period-only stats requests
        "today",
        "yesterday",
        "week",
        "weekly",
        "this week",
        "month",
        "monthly",
        "this month"
    }

    if text in stats_phrases:
        return True

    if text.startswith("stats "):
        return True

    if text.startswith("my stats "):
        return True

    if text.startswith("what did i train "):
        return True

    if text.startswith("what did i do "):
        return True

    if text.startswith("how many days"):
        return True

    if text.startswith("how many exercises"):
        return True

    return False

def is_stats_choice_message(message):

    text = message.lower().strip()

    return text in {
        "stats",
        "my stats",
        "show my stats",
        "show me my stats",
        "show me stats",
        "my progress",
        "show my progress"
    }


def parse_stats_choice(message):

    text = message.lower().strip()

    if text in {
        "training",
        "training stats",
        "workout",
        "workout stats",
        "exercise",
        "exercise stats"
    }:
        return "training"

    if text in {
        "food",
        "food stats",
        "nutrition",
        "nutrition stats",
        "meals",
        "meal stats"
    }:
        return "food"

    return None



def parse_stats_period(message):

    text = message.lower().strip()

    # Today
    if "today" in text:
        return {
            "type": "today",
            "days": 1,
            "label": "Today"
        }

    # Yesterday
    if "yesterday" in text:
        return {
            "type": "yesterday",
            "days": 1,
            "label": "Yesterday"
        }

    # Week
    if any(word in text for word in [
        "week",
        "weekly"
    ]):
        return {
            "type": "week",
            "days": 7,
            "label": "This Week"
        }

    # Month
    if any(word in text for word in [
        "month",
        "monthly"
    ]):
        return {
            "type": "month",
            "days": 30,
            "label": "This Month"
        }

    return None


def get_stats_date(period):

    if period["type"] == "today":
        return datetime.now().date().isoformat()

    if period["type"] == "yesterday":
        return (
            datetime.now().date() - timedelta(days=1)
        ).isoformat()

    return None


# def build_stats_response(
#     user_number,
#     message
# ):

#     text = message.lower().strip()

#     # ========================================================
#     # MUSCLE STATS
#     # ========================================================

#     muscle_words = {
#         "chest": "chest",
#         "back": "back",
#         "shoulder": "shoulders",
#         "shoulders": "shoulders",
#         "biceps": "biceps",
#         "triceps": "triceps",
#         "arms": "arms",
#         "legs": "legs",
#         "leg": "legs",
#         "abs": "abs",
#         "glutes": "glutes",
#         "hamstrings": "hamstrings",
#         "quadriceps": "quadriceps",
#         "quads": "quadriceps",
#         "calves": "calves"
#     }

#     for word, target in muscle_words.items():

#         if word not in text:
#             continue

#         if not any(
#             phrase in text
#             for phrase in [
#                 "how many",
#                 "times",
#                 "train",
#                 "trained",
#                 "workout",
#                 "workouts"
#             ]
#         ):
#             continue

#         rows = get_muscle_stats(
#             user_number,
#             target
#         )

#         if not rows:

#             return (
#                 f"📊 You haven't completed "
#                 f"any {target} exercises yet."
#             )

#         unique_days = len({
#             row["training_date"]
#             for row in rows
#         })

#         lines = [
#             f"📊 {target.title()} Stats",
#             "",
#             f"🏋️ Training days: {unique_days}",
#             f"💪 Exercises completed: {len(rows)}",
#             "",
#             "Recent:"
#         ]

#         for row in rows[:15]:

#             lines.append(
#                 f"• {row['training_date']} — "
#                 f"{row['exercise_name']}"
#             )

#         return "\n".join(lines)

#     # ========================================================
#     # PERIOD
#     # ========================================================

#     days = None

#     if "today" in text:
#         days = 1

#     elif "this week" in text:
#         days = 7

#     elif "week" in text:
#         days = 7

#     elif "this month" in text:
#         days = 30

#     elif "month" in text:
#         days = 30

#     if days:

#         rows = get_exercises_by_period(
#             user_number,
#             days
#         )

#         if not rows:

#             return (
#                 "📊 No completed workouts "
#                 "found for this period."
#             )

#         training_days = sorted({
#             row["training_date"]
#             for row in rows
#         })

#         lines = [
#             "📊 Training Stats",
#             "",
#             f"🏋️ Training days: "
#             f"{len(training_days)}",
#             f"💪 Exercises completed: "
#             f"{len(rows)}",
#             "",
#             "Exercises:"
#         ]

#         for row in rows[:20]:

#             lines.append(
#                 f"• {row['training_date']} — "
#                 f"{row['exercise_name']}"
#             )

#         return "\n".join(lines)

#     # ========================================================
#     # OVERALL STATS
#     # ========================================================

#     stats = get_stats(
#         user_number
#     )

#     if stats["total_days"] == 0:

#         return (
#             "📊 You don't have any "
#             "completed workouts yet.\n\n"
#             "Complete a workout and I'll "
#             "start tracking your progress. 💪"
#         )

#     lines = [
#         "📊 Your Training Stats",
#         "",
#         f"🏋️ Training days: "
#         f"{stats['total_days']}",
#         f"💪 Exercises completed: "
#         f"{stats['total_exercises']}",
#         ""
#     ]

#     if stats["recent_sessions"]:
#         lines.append("Recent workouts:")

#         current_date = None
#         current_exercise = None

#         for row in stats["recent_sessions"]:

#             # New workout date
#             if row["training_date"] != current_date:
#                 current_date = row["training_date"]
#                 current_exercise = None

#                 lines.append(
#                     f"\n📅 {current_date}"
#                 )

#             # New exercise
#             if row["exercise_name"] != current_exercise:
#                 current_exercise = row["exercise_name"]

#                 lines.append(
#                     f"\n• {current_exercise}"
#                 )

#             # Set information
#             if row["set_number"] is not None:

#                 weight = row["weight"]
#                 reps = row["reps"]
#                 duration = row["duration_seconds"]

#                 if weight is not None and reps is not None:
#                     lines.append(
#                         f"   Set {row['set_number']}: "
#                         f"{weight:g} kg × {reps} reps"
#                     )

#                 elif reps is not None:
#                     lines.append(
#                         f"   Set {row['set_number']}: "
#                         f"{reps} reps"
#                     )

#                 elif duration is not None:
#                     lines.append(
#                         f"   Set {row['set_number']}: "
#                         f"{duration} sec"
#                     )
#     return "\n".join(lines)


def build_stats_response(
    user_number,
    message
):

    text = message.lower().strip()

    # ========================================================
    # MUSCLE STATS
    # ========================================================

    muscle_words = {
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
        "glutes": "glutes",
        "hamstrings": "hamstrings",
        "quadriceps": "quadriceps",
        "quads": "quadriceps",
        "calves": "calves"
    }

    for word, target in muscle_words.items():

        if word not in text:
            continue

        if not any(
            phrase in text
            for phrase in [
                "how many",
                "times",
                "train",
                "trained",
                "workout",
                "workouts"
            ]
        ):
            continue

        rows = get_muscle_stats(
            user_number,
            target
        )

        if not rows:

            return (
                f"📊 You haven't completed "
                f"any {target} exercises yet."
            )

        unique_days = len({
            row["training_date"]
            for row in rows
        })

        lines = [
            f"📊 {target.title()} Stats",
            "",
            f"🏋️ Training days: {unique_days}",
            f"💪 Exercises completed: {len(rows)}",
            "",
            "Recent:"
        ]

        for row in rows[:15]:

            lines.append(
                f"• {row['training_date']} — "
                f"{row['exercise_name']}"
            )

        return "\n".join(lines)

    # ========================================================
    # PERIOD
    # ========================================================

    period = parse_stats_period(
        message
    )

    if period:

        if period["type"] in {"today", "yesterday"}:

            stats_date = get_stats_date(period)

            rows = get_exercises_by_date(
                user_number,
                stats_date
            )

        else:

            days = period["days"]

            rows = get_exercises_by_period(
                user_number,
                days
            )

        if not rows:

            return (
                "📊 No completed workouts "
                f"found for {period['label'].lower()}."
            )

        training_days = sorted({
            row["training_date"]
            for row in rows
        })

        lines = [
            "📊 Training Stats",
            "",
            f"📅 Period: {period['label']}",
            f"🏋️ Training days: "
            f"{len(training_days)}",
            f"💪 Exercises completed: "
            f"{len(rows)}",
            "",
            "Exercises:"
        ]

        for row in rows[:20]:

            lines.append(
                f"• {row['training_date']} — "
                f"{row['exercise_name']}"
            )

        return "\n".join(lines)

    # ========================================================
    # OVERALL STATS
    # ========================================================

    stats = get_stats(
        user_number
    )

    if stats["total_days"] == 0:

        return (
            "📊 You don't have any "
            "completed workouts yet.\n\n"
            "Complete a workout and I'll "
            "start tracking your progress. 💪"
        )

    lines = [
        "📊 Your Training Stats",
        "",
        f"🏋️ Training days: "
        f"{stats['total_days']}",
        f"💪 Exercises completed: "
        f"{stats['total_exercises']}",
        ""
    ]

    if stats["recent_sessions"]:
        lines.append("Recent workouts:")

        current_date = None
        current_exercise = None

        for row in stats["recent_sessions"]:

            # New workout date
            if row["training_date"] != current_date:
                current_date = row["training_date"]
                current_exercise = None

                lines.append(
                    f"\n📅 {current_date}"
                )

            # New exercise
            if row["exercise_name"] != current_exercise:
                current_exercise = row["exercise_name"]

                lines.append(
                    f"\n• {current_exercise}"
                )

            # Set information
            if row["set_number"] is not None:

                weight = row["weight"]
                reps = row["reps"]
                duration = row["duration_seconds"]

                if weight is not None and reps is not None:
                    lines.append(
                        f"   Set {row['set_number']}: "
                        f"{weight:g} kg × {reps} reps"
                    )

                elif reps is not None:
                    lines.append(
                        f"   Set {row['set_number']}: "
                        f"{reps} reps"
                    )

                elif duration is not None:
                    lines.append(
                        f"   Set {row['set_number']}: "
                        f"{duration} sec"
                    )

    return "\n".join(lines)


def is_execution_message(message):

    text = message.lower().strip()

    execution_phrases = [
        "how do i do",
        "how do i execute",
        "how to do",
        "how to execute",
        "how can i do",
        "how can i execute",
        "how should i do",
        "how should i execute",
        "show me how to do",
        "show me how to execute",
        "how is this exercise done",
        "how is this exercise executed",
        "show me how",
        "show me",
        "how do i perform",
        "how to perform"
    ]

    return any(
        phrase in text
        for phrase in execution_phrases
    )


def extract_execution_exercise(
    message,
    user_number
):

    text = message.lower().strip()

    prefixes = [
        "how do i do ",
        "how do i execute ",
        "how to do ",
        "how to execute ",
        "how can i do ",
        "how can i execute ",
        "how should i do ",
        "how should i execute ",
        "show me how to do ",
        "show me how to execute ",
        "how do i perform ",
        "how to perform "
    ]

    for prefix in prefixes:

        if text.startswith(prefix):

            return text[
                len(prefix):
            ].strip()

    if text in {
        "show me how",
        "show me",
        "how do i do it",
        "how do i perform it",
        "how do i execute it",
        "how to do it",
        "how to perform it"
    }:

        last_exercise = last_sent_exercises.get(
            user_number
        )

        if last_exercise:

            return last_exercise["exercise_name"]

    return None



# ============================================================
# LANGUAGE QUIZ
# ============================================================

def normalize_quiz_answer(text):
    """
    Normalize an answer so small differences don't matter.
    """

    text = text.lower().strip()

    # Remove punctuation
    text = re.sub(
        r"[^\w\s-]",
        "",
        text
    )

    # Normalize spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def is_quiz_command(message):

    text = message.lower().strip()

    return text in {
        "quiz",
        "language quiz",
        "vocabulary quiz",
        "review",
        "review words"
    }


def start_quiz(
    user_id,
    language
):
    """
    Start a quiz using words that were already shown
    to this user.
    """

    level = get_language_level(
        language
    )

    words = get_quiz_words(
        user_id=user_id,
        language=language,
        level=level,
        limit=10
    )

    if not words:
        return None

    # Select one random word
    word = words[0]

    pending_language_quiz[user_id] = {
        "vocabulary_id": word["id"],
        "word": word["word"],
        "expected": word["translation"],
        "language": language,
        "level": level
    }

    return {
        "word": word["word"],
        "language": language,
        "level": level
    }


def answer_quiz(
    user_id,
    answer
):
    """
    Check the user's answer against the active quiz.
    """

    quiz = pending_language_quiz.get(
        user_id
    )

    if not quiz:
        return None

    expected = quiz["expected"]

    if not expected:
        pending_language_quiz.pop(
            user_id,
            None
        )
        return None

    user_answer = normalize_quiz_answer(
        answer
    )

    expected_answer = normalize_quiz_answer(
        expected
    )

    correct = (
        user_answer == expected_answer
    )

    result = update_quiz_result(
        user_id=user_id,
        vocabulary_id=quiz["vocabulary_id"],
        correct=correct
    )

    pending_language_quiz.pop(
        user_id,
        None
    )

    return {
        "correct": correct,
        "word": quiz["word"],
        "expected": expected,
        "mastery": result["mastery"],
        "review_count": result["review_count"]
    }
    

def send_scenario_phrase_audio(
    user_number,
    text,
    language,
    filename
):
    """
    Generate and send pronunciation audio
    for a scenario phrase.
    """

    try:

        audio_path = generate_audio(
            text=text,
            language=language,
            filename=filename
        )

        if not audio_path:
            return

        if not NGROK_URL:
            print("NGROK_URL is not configured.")
            return

        audio_filename = Path(
            audio_path
        ).name

        audio_url = (
            f"{NGROK_URL}"
            f"/language-audio/"
            f"{audio_filename}"
        )

        print(
            "Sending scenario audio:",
            audio_url
        )

        send_whatsapp_audio(
            user_number,
            audio_url
        )

    except Exception as error:

        print(
            f"Scenario TTS error: {error}"
        )
def format_scenario(
    scenario,
    language
):
    """
    Format a language-learning scenario
    for WhatsApp.
    """

    lines = [
        f"{scenario['icon']} *{scenario['title']}*",
        ""
    ]

    for index, situation in enumerate(
        scenario["situations"],
        start=1
    ):

        lines.append(
            f"🎯 *Situation {index}*"
        )

        lines.append(
            situation["situation"]
        )

        lines.append("")

        for phrase in situation["phrases"]:

            lines.append(
                f"🇵🇱 *{phrase['text']}*"
            )

            lines.append(
                f"🇬🇧 {phrase['translation']}"
            )

            lines.append("")

    return "\n".join(lines)


@app.route("/language-audio/<path:filename>")
def serve_language_audio(filename):

    return send_from_directory(
        LANGUAGE_AUDIO_DIR,
        filename
    )
# ============================================================
# WHATSAPP WEBHOOK
# ============================================================

@app.route(
    "/whatsapp",
    methods=["POST"]
)
def whatsapp_webhook():

    incoming_message = request.form.get(
        "Body",
        ""
    ).strip()

    sender = request.form.get(
        "From",
        ""
    )

    user_number = sender.replace(
        "whatsapp:",
        ""
    )
    
    # ========================================================
    # STATS CHOICE
    #
    # User previously asked:
    # "show stats"
    #
    # Now they choose:
    # "training"
    # or
    # "food"
    # ========================================================

    # ========================================================
    # STATS CHOICE
    # ========================================================

    if user_number in pending_stats_choice:

        choice = parse_stats_choice(
            incoming_message
        )

        if not choice:

            send_whatsapp_message(
                user_number,
                (
                    "📊 Please choose one:\n\n"
                    "🏋️ *training*\n"
                    "🍽️ *food*"
                )
            )

            return Response(
                "OK",
                status=200
            )

        pending_stats_choice.pop(
            user_number,
            None
        )

        # ====================================================
        # TRAINING
        # ====================================================

        if choice == "training":

            pending_stats_period[
                user_number
            ] = "training"

            send_whatsapp_message(
                user_number,
                (
                    "🏋️ *Training stats*\n\n"
                    "What period would you like?\n\n"
                    "📅 *today*\n"
                    "📅 *yesterday*\n"
                    "📅 *weekly*\n"
                    "📅 *monthly*"
                )
            )

            return Response(
                "OK",
                status=200
            )

        # ====================================================
        # FOOD
        # ====================================================

        if choice == "food":

            pending_stats_period[
                user_number
            ] = "food"

            send_whatsapp_message(
                user_number,
                (
                    "🍽️ *Food stats*\n\n"
                    "What period would you like?\n\n"
                    "📅 *today*\n"
                    "📅 *yesterday*\n"
                    "📅 *weekly*\n"
                    "📅 *monthly*"
                )
            )

            return Response(
                "OK",
                status=200
            )

    # ========================================================
    # STATS PERIOD
    # ========================================================

    if user_number in pending_stats_period:

        period = parse_stats_period(
            incoming_message
        )

        if not period:

            send_whatsapp_message(
                user_number,
                (
                    "📅 Please choose a period:\n\n"
                    "• *today*\n"
                    "• *yesterday*\n"
                    "• *weekly*\n"
                    "• *monthly*"
                )
            )

            return Response(
                "OK",
                status=200
            )

        stats_type = pending_stats_period.pop(
            user_number
        )

 
        if stats_type == "training":

            try:
                answer = build_stats_response(
                    user_number,
                    incoming_message
                )

                send_whatsapp_message(
                    user_number,
                    answer
                )

            except Exception as e:
                print("Training stats error:", e)

                send_whatsapp_message(
                    user_number,
                    "Sorry, I couldn't load your training stats."
                )

            return Response(
                "OK",
                status=200
            )


        elif stats_type == "food":

            try:

                stats_date = get_stats_date(
                    period
                )

                if stats_date:

                    nutrition = get_nutrition_by_date(
                        user_number,
                        stats_date
                    )

                    answer = (
                        f"🍽️ *Food Stats — {period['label']}*\n\n"
                        f"🍴 Meals: {nutrition['meals']}\n"
                        f"🔥 Calories: {nutrition['calories']:g} kcal\n"
                        f"💪 Protein: {nutrition['protein']:g} g\n"
                        f"🍚 Carbs: {nutrition['carbs']:g} g\n"
                        f"🥑 Fat: {nutrition['fat']:g} g"
                    )

                else:

                    # Weekly / monthly
                    nutrition = get_nutrition_by_period(
                        user_number,
                        period["days"]
                    )

                    answer = (
                        f"🍽️ *Food Stats — {period['label']}*\n\n"
                        f"🍴 Meals: {nutrition['meals']}\n"
                        f"🔥 Calories: {nutrition['calories']:g} kcal\n"
                        f"💪 Protein: {nutrition['protein']:g} g\n"
                        f"🍚 Carbs: {nutrition['carbs']:g} g\n"
                        f"🥑 Fat: {nutrition['fat']:g} g"
                    )

                send_whatsapp_message(
                    user_number,
                    answer
                )

            except Exception as e:

                print(
                    "Food stats error:",
                    e
                )

                send_whatsapp_message(
                    user_number,
                    "Sorry, I couldn't load your food stats."
                )

            return Response(
                "OK",
                status=200
            )
    
    # ========================================================
    # LANGUAGE LEARNING
    # ========================================================
    #
    # Commands:
    #
    # language
    # language polish
    # language french
    # language english
    # word
    # quiz
    #
    # ========================================================

    language_message = incoming_message.lower().strip()


    # ========================================================
    # QUIZ ANSWER
    #
    # IMPORTANT:
    # This must happen BEFORE normal commands.
    #
    # Example:
    #
    # Bot:
    # 🧠 What does "dom" mean?
    #
    # User:
    # house
    #
    # ========================================================

    if user_number in pending_language_quiz:

        result = answer_quiz(
            user_id=user_number,
            answer=incoming_message
        )

        if result:

            if result["correct"]:

                reply = (
                    "✅ *Correct!*\n\n"
                    f"🇵🇱 {result['word']}\n"
                    f"🇬🇧 {result['expected']}\n\n"
                    f"⭐ Mastery: "
                    f"{result['mastery']}/5\n\n"
                    "Type *quiz* for another question."
                )

            else:

                reply = (
                    "❌ *Not quite!*\n\n"
                    f"🇵🇱 {result['word']}\n"
                    f"🇬🇧 Correct answer: "
                    f"{result['expected']}\n\n"
                    f"⭐ Mastery: "
                    f"{result['mastery']}/5\n\n"
                    "Type *quiz* for another question."
                )

            send_whatsapp_message(
                user_number,
                reply
            )

            return Response(
                "OK",
                status=200
            )


    # ========================================================
    # QUIZ COMMAND
    # ========================================================

    if is_quiz_command(
        incoming_message
    ):

        selected_language = get_user_language(
            user_id=user_number,
            default="polish"
        )

        try:

            quiz = start_quiz(
                user_id=user_number,
                language=selected_language
            )

            if not quiz:

                send_whatsapp_message(
                    user_number,
                    (
                        "📚 You don't have any "
                        "words ready for review yet.\n\n"
                        "Use *word* to learn a new word first."
                    )
                )

                return Response(
                    "OK",
                    status=200
                )

            # Language flag
            flags = {
                "polish": "🇵🇱",
                "french": "🇫🇷",
                "english": "🇬🇧"
            }

            flag = flags.get(
                selected_language,
                "🌍"
            )

            # The question is always translation
            # into English.
            send_whatsapp_message(
                user_number,
                (
                    "🧠 *Vocabulary Quiz*\n\n"
                    f"{flag} *{quiz['word']}*\n\n"
                    "What does this word mean in English?\n\n"
                    "✏️ Reply with your answer."
                )
            )

        except Exception as e:

            print(
                "Language quiz error:",
                e
            )

            send_whatsapp_message(
                user_number,
                "Sorry, I couldn't start the vocabulary quiz."
            )

        return Response(
            "OK",
            status=200
        )


    # ============================================================
    # LANGUAGE SCENARIO
    # ============================================================

    if language_message == "scenario":

        selected_language = get_user_language(
            user_id=user_number,
            default="polish"
        )

        scenario = get_random_scenario()

        if not scenario:

            send_whatsapp_message(
                user_number,
                "Sorry, no language scenarios are available."
            )

            return Response(
                "OK",
                status=200
            )

        # Send text
        message_text = format_scenario(
            scenario=scenario,
            language=selected_language
        )

        send_whatsapp_message(
            user_number,
            message_text
        )

        # Send phrase audio
        audio_index = 1

        for situation in scenario["situations"]:

            for phrase in situation["phrases"]:

                send_scenario_phrase_audio(
                    user_number=user_number,
                    text=phrase["text"],
                    language=selected_language,
                    filename=(
                        f"scenario_"
                        f"{scenario.get('name', 'random')}_"
                        f"{audio_index}.mp3"
                    )
                )

                audio_index += 1

        return Response(
            "OK",
            status=200
        )

    if language_message.startswith("scenario "):

        scenario_name = language_message[
            len("scenario "):
        ].strip()

        selected_language = get_user_language(
            user_id=user_number,
            default="polish"
        )

        scenario = get_scenario(
            scenario_name
        )

        if not scenario:

            available = ", ".join(
                get_scenario_names()
            )

            send_whatsapp_message(
                user_number,
                "Unknown scenario.\n\n"
                f"Available scenarios:\n{available}"
            )

            return Response(
                "OK",
                status=200
            )

        # Send text
        message_text = format_scenario(
            scenario=scenario,
            language=selected_language
        )

        send_whatsapp_message(
            user_number,
            message_text
        )

        # Send pronunciation audio
        audio_index = 1

        for situation in scenario["situations"]:

            for phrase in situation["phrases"]:

                send_scenario_phrase_audio(
                    user_number=user_number,
                    text=phrase["text"],
                    language=selected_language,
                    filename=(
                        f"scenario_"
                        f"{scenario_name}_"
                        f"{audio_index}.mp3"
                    )
                )

                audio_index += 1

        return Response(
            "OK",
            status=200
        )
    # ========================================================
    # SHOW LANGUAGE SETTINGS
    # ========================================================

    if language_message == "language":

        english_level = get_language_level(
            "english"
        )

        french_level = get_language_level(
            "french"
        )

        polish_level = get_language_level(
            "polish"
        )

        send_whatsapp_message(
            user_number,
            (
                "🌍 *Language Learning*\n\n"
                f"🇬🇧 English — *{english_level}*\n"
                f"🇫🇷 French — *{french_level}*\n"
                f"🇵🇱 Polish — *{polish_level}*\n\n"
                "Commands:\n"
                "• *word* — learn a new word\n"
                "• *quiz* — review learned words\n"
                "• *language polish*\n"
                "• *language french*\n"
                "• *language english*"
            )
        )

        return Response(
            "OK",
            status=200
        )


    # ========================================================
    # SELECT LANGUAGE
    # ========================================================

    if language_message.startswith(
        "language "
    ):

        selected_language = language_message.replace(
            "language ",
            "",
            1
        ).strip()

        supported_languages = get_supported_languages()

        if selected_language not in supported_languages:

            send_whatsapp_message(
                user_number,
                (
                    "🌍 Supported languages:\n\n"
                    "🇬🇧 *english*\n"
                    "🇫🇷 *french*\n"
                    "🇵🇱 *polish*"
                )
            )

            return Response(
                "OK",
                status=200
            )

        set_user_language(
            user_id=user_number,
            language=selected_language
        )

        level = get_language_level(
            selected_language
        )

        send_whatsapp_message(
            user_number,
            (
                f"🌍 Language changed to "
                f"*{selected_language.capitalize()}*.\n\n"
                f"Your level: *{level}*\n\n"
                "Send *word* to learn a new word."
            )
        )

        return Response(
            "OK",
            status=200
        )


    # ========================================================
    # DAILY WORD
    # ========================================================

    if language_message == "word":

        selected_language = get_user_language(
            user_id=user_number,
            default="polish"
        )

        try:

            daily_word = get_daily_word(
                language=selected_language,
                user_id=user_number
            )

            if not daily_word:

                send_whatsapp_message(
                    user_number,
                    (
                        "📚 I don't have any more "
                        f"{selected_language} words "
                        "available for your level."
                    )
                )

                return Response(
                    "OK",
                    status=200
                )

            flags = {
                "polish": "🇵🇱",
                "french": "🇫🇷",
                "english": "🇬🇧"
            }

            flag = flags.get(
                selected_language,
                "🌍"
            )

            answer_lines = [
                "📚 *Word of the Day*",
                "",
                f"{flag} *{daily_word['word']}*",
                f"📊 Level: *{daily_word['level']}*",
                ""
            ]

            if daily_word["translation"]:

                answer_lines.append(
                    f"🇬🇧 Translation: "
                    f"{daily_word['translation']}"
                )

            if daily_word["part_of_speech"]:

                answer_lines.append(
                    f"🏷️ Type: "
                    f"{daily_word['part_of_speech']}"
                )

            if daily_word["pronunciation"]:

                answer_lines.append(
                    f"🔊 Pronunciation: "
                    f"{daily_word['pronunciation']}"
                )

            if daily_word["definition"]:

                answer_lines.extend([
                    "",
                    f"📖 Definition: "
                    f"{daily_word['definition']}"
                ])

            if daily_word["example_sentence"]:

                answer_lines.extend([
                    "",
                    "💬 *Example:*",
                    daily_word["example_sentence"]
                ])

            if daily_word["example_translation"]:

                answer_lines.append(
                    f"🇬🇧 "
                    f"{daily_word['example_translation']}"
                )

            # Important:
            # get_daily_word() already records this word
            # in learned_words.
            answer_lines.extend([
                "",
                "🧠 This word is now added "
                "to your quiz."
            ])

            send_whatsapp_message(
                user_number,
                "\n".join(answer_lines)
            )
            # ============================================================
            # WORD AUDIO
            # ============================================================

            audio_path = daily_word.get("audio_path")

            if audio_path and NGROK_URL:

                try:

                    audio_filename = Path(
                        audio_path
                    ).name

                    audio_url = (
                        f"{NGROK_URL}"
                        f"/language-audio/"
                        f"{audio_filename}"
                    )

                    print(
                        "Sending word pronunciation:",
                        audio_url
                    )

                    send_whatsapp_audio(
                        user_number,
                        audio_url
                    )

                except Exception as e:

                    print(
                        "Word pronunciation error:",
                        e
                    )


            # ============================================================
            # EXAMPLE AUDIO
            # ============================================================

            example_audio_path = daily_word.get(
                "example_audio_path"
            )

            if example_audio_path and NGROK_URL:

                try:

                    example_audio_filename = Path(
                        example_audio_path
                    ).name

                    example_audio_url = (
                        f"{NGROK_URL}"
                        f"/language-audio/"
                        f"{example_audio_filename}"
                    )

                    print(
                        "Sending example pronunciation:",
                        example_audio_url
                    )

                    send_whatsapp_audio(
                        user_number,
                        example_audio_url
                    )

                except Exception as e:

                    print(
                        "Example pronunciation error:",
                        e
                    )
        except Exception as e:

            print(
                "Language word error:",
                e
            )

            send_whatsapp_message(
                user_number,
                "Sorry, I couldn't get your vocabulary word."
            )

        return Response(
            "OK",
            status=200
        )
    # ========================================================
    # YOUR EXISTING CODE CONTINUES HERE
    # ========================================================

    # meal tracking
    # set tracking
    # workout handling
    # etc.

    if is_meal_message(incoming_message):

        meal = parse_meal_message(
            incoming_message
        )

        if not meal:
            send_whatsapp_message(
                user_number,
                (
                    "🍽️ I couldn't understand the meal.\n\n"
                    "Try something like:\n"
                    "*I ate 200g chicken breast*"
                )
            )

            return Response("OK", status=200)

        try:
            result = log_meal(
                user_number=user_number,
                foods=meal["foods"]
            )

            if not result:
                send_whatsapp_message(
                    user_number,
                    (
                        "🔎 I couldn't find any of "
                        "the foods in USDA.\n\n"
                        "Please try using a more specific "
                        "food name and quantity."
                    )
                )

                return Response("OK", status=200)

            answer_lines = [
                "🍽️ Meal recorded!",
                ""
            ]

            for item in result["items"]:
                answer_lines.append(
                    f"🥗 {item['food_name']}"
                )
                answer_lines.append(
                    f"⚖️ {item['quantity']:g} g"
                )
                answer_lines.append(
                    f"🔥 {item['calories']:g} kcal"
                )
                answer_lines.append(
                    f"💪 {item['protein']:g} g protein"
                )
                answer_lines.append("")

            answer_lines.extend([
                "──────────────",
                f"🔥 Total: {result['total_calories']:g} kcal",
                f"💪 Protein: {result['total_protein']:g} g",
                f"🍚 Carbs: {result['total_carbs']:g} g",
                f"🥑 Fat: {result['total_fat']:g} g"
            ])

            answer = "\n".join(answer_lines)
            send_whatsapp_message(
                user_number,
                answer
            )

        except Exception as e:
            print("Meal error:", e)

            send_whatsapp_message(
                user_number,
                "Sorry, I couldn't record that meal."
            )

        return Response("OK", status=200)
    
    # --------------------------------------------------
    # ACTIVE SET TRACKING
    # --------------------------------------------------

    if user_number in pending_set_tracking:
        if incoming_message.lower().strip() != "done":
            if handle_set_tracking(user_number, incoming_message):
                return Response("OK", status=200)

    # --------------------------------------------------
    # START SET TRACKING
    # --------------------------------------------------

    set_request = parse_exercise_set_request(incoming_message)

    if set_request:
        exercise_name, sets_count = set_request

        if start_set_tracking(
            user_number,
            exercise_name,
            sets_count
        ):
            return Response("OK", status=200)

        send_whatsapp_message(
            user_number,
            f"❌ I couldn't find '{exercise_name}' "
            "in your current workout."
        )

        return Response("OK", status=200)
    print()
    print("=" * 60)
    print("WhatsApp:", incoming_message)
    print("From:", user_number)
    print("=" * 60)

    # ========================================================
    # STATS: WORKOUT COMPLETED
    # ========================================================

    
    if is_completion_message(
        incoming_message
    ):

        # Stop active set tracking
        pending_set_tracking.pop(
            user_number,
            None
        )

        result = complete_pending_workout(
            user_number
        )

        if not result:

            send_whatsapp_message(
                user_number,
                (
                    "I don't have a pending "
                    "workout to mark as completed. 💪"
                )
            )

            return Response(
                "OK",
                status=200
            )

        exercises_text = "\n".join(
            f"• {name}"
            for name in result["exercises"]
        )

        send_whatsapp_message(
            user_number,
            (
                "✅ Workout completed!\n\n"
                f"I recorded "
                f"{result['count']} exercises:\n"
                f"{exercises_text}\n\n"
                "📊 Your progress has been updated."
            )
        )

        return Response(
            "OK",
            status=200
        )

    # ========================================================
    # HOW TO EXECUTE EXERCISE
    #
    # Example:
    # User: How do I execute Crunch?
    # Bot: [Crunch mp4]
    # ========================================================

    if is_execution_message(
        incoming_message
    ):

        exercise_name = extract_execution_exercise(
            incoming_message,
            user_number
        )

        print(
            "Execution request:",
            exercise_name
        )

        if not exercise_name:

            send_whatsapp_message(
                user_number,
                (
                    "Sure! 💪 Tell me which exercise "
                    "you want to learn.\n\n"
                    "For example:\n"
                    "How do I execute Crunch?"
                )
            )

            return Response(
                "OK",
                status=200
            )

        # IMPORTANT:
        # Do NOT exclude trained exercises here.
        # A user should be able to ask how to perform
        # an exercise even if they already completed it.

        exercise = find_exact_exercise(
            exercise_name
        )

        if not exercise:

            send_whatsapp_message(
                user_number,
                (
                    f"Sorry 😕 I don't have "
                    f"{exercise_name} in my "
                    f"exercise library yet."
                )
            )

            return Response(
                "OK",
                status=200
            )

        actual_name = exercise.get(
            "exercise_name",
            exercise_name
        )

        filename = exercise.get(
            "filename"
        )

        try:

            mp4_url = get_mp4_url(
                filename
            )

            print(
                "Sending exercise mp4:",
                actual_name
            )

            print(
                "mp4 URL:",
                mp4_url
            )

            send_whatsapp_mp4(
                user_number,
                mp4_url,
                caption=f"🎥 How to perform {actual_name}"
            )

        except Exception as e:

            print(
                "mp4 sending error:",
                e
            )

            send_whatsapp_message(
                user_number,
                (
                    "I found the exercise, but "
                    "couldn't send the demonstration mp4."
                )
            )

        return Response(
            "OK",
            status=200
        )
        
    # ========================================================
    # STATS REQUEST
    # ========================================================

    # ========================================================
    # STATS REQUEST
    # ========================================================

    # Generic stats request:
    #
    # User: show stats
    #
    # Bot:
    # 📊 What stats would you like to see?
    # 🏋️ Training stats
    # 🍽️ Food stats
    #
    # We only do this for generic stats requests.
    # Specific requests like "training stats this week"
    # still go directly to build_stats_response().
    # ========================================================

    if is_stats_choice_message(
        incoming_message
    ):

        pending_stats_choice[
            user_number
        ] = True

        send_whatsapp_message(
            user_number,
            (
                "📊 What stats would you like to see?\n\n"
                "🏋️ *Training stats*\n"
                "🍽️ *Food stats*\n\n"
                "Reply with *training* or *food*."
            )
        )

        return Response(
            "OK",
            status=200
        )

    # --------------------------------------------------------
    # SPECIFIC TRAINING STATS
    # --------------------------------------------------------

    if is_stats_message(
        incoming_message
    ):

        try:

            answer = build_stats_response(
                user_number,
                incoming_message
            )

            send_whatsapp_message(
                user_number,
                answer
            )

        except Exception as e:

            print(
                "Stats error:",
                e
            )

            send_whatsapp_message(
                user_number,
                "Sorry, I couldn't load your stats."
            )

        return Response(
            "OK",
            status=200
        )
    
    # ========================================================
    # 1. USER IS ANSWERING "HOW MANY?"
    # ========================================================

    if user_number in pending_workouts:

        try:

            count = int(
                incoming_message
            )

        except ValueError:

            # Important:
            # Don't lose the pending workout.
            send_whatsapp_message(
                user_number,
                (
                    "Please send me a number "
                    "between 1 and 20.\n\n"
                    "For example: 5"
                )
            )

            return Response(
                "OK",
                status=200
            )

        if count < 1 or count > 20:

            send_whatsapp_message(
                user_number,
                (
                    "Please choose between "
                    "1 and 20 exercises."
                )
            )

            return Response(
                "OK",
                status=200
            )

        # Get pending workout
        workout = pending_workouts.pop(
            user_number
        )

        target = workout[
            "target"
        ]

        print(
            f"Workout: {target}"
        )

        print(
            f"Requested count: {count}"
        )

        # Find exercises that have NOT already been completed
        trained_filenames = get_trained_exercise_filenames(
            user_number
        )

        print(
            "TRAINED FILENAMES:",
            trained_filenames
        )

        exercises = find_exercises(
            target=target,
            count=count,
            exclude_filenames=trained_filenames
        )

        print(
            f"Found: {len(exercises)}"
        )

        # ----------------------------------------------------
        # NO RESULTS
        # ----------------------------------------------------

        if not exercises:

            send_whatsapp_message(
                user_number,
                (
                    f"Sorry, I couldn't find "
                    f"any {target} exercises "
                    f"in my library."
                )
            )

            return Response(
                "OK",
                status=200
            )

        # ----------------------------------------------------
        # INFORM USER
        # ----------------------------------------------------

        if len(exercises) < count:

            send_whatsapp_message(
                user_number,
                (
                    f"I found only "
                    f"{len(exercises)} matching "
                    f"{target} exercises."
                )
            )

        else:

            send_whatsapp_message(
                user_number,
                (
                    f"Here are your "
                    f"{count} {target} exercises 💪"
                )
            )

        # ----------------------------------------------------
        # SEND IMAGES
        # ----------------------------------------------------
        # ----------------------------------------------------
        # CREATE PENDING WORKOUT
        # ----------------------------------------------------

        pending_id = start_pending_workout(
            user_number,
            target=target,
            count=len(exercises)
        )

        print(
            "Created pending workout:",
            pending_id
        )

        # ----------------------------------------------------
        # SEND IMAGES + SAVE SENT EXERCISES
        # ----------------------------------------------------

        for exercise in exercises:

            try:

                send_exercise(
                    user_number,
                    exercise
                )

                add_pending_exercise(
                    pending_id,
                    exercise.get(
                        "exercise_name",
                        "Exercise"
                    ),
                    exercise.get(
                        "filename"
                    ),
                    target
                )

                print(
                    "Saved pending exercise:",
                    exercise.get(
                        "exercise_name",
                        "Exercise"
                    )
                )

            except Exception as e:

                print(
                    "Image sending error:",
                    e
                )

        return Response(
            "OK",
            status=200
        )


    # ========================================================
    # 2. DETECT INTENT
    # ========================================================

    try:

        intent = detect_intent(
            incoming_message
        )

        print(
            "Detected intent:",
            json.dumps(
                intent,
                indent=2
            )
        )

    except Exception as e:

        print(
            "Intent detection error:",
            e
        )

        send_whatsapp_message(
            user_number,
            (
                "Sorry, I couldn't understand "
                "your message."
            )
        )

        return Response(
            "OK",
            status=200
        )


    intent_type = intent.get(
        "intent"
    )


    # ========================================================
    # 3. NORMAL CHAT
    # ========================================================

    if intent_type == "chat":

        try:

            answer = ai_response(
                incoming_message
            )

            send_whatsapp_message(
                user_number,
                answer
            )

        except Exception as e:

            print(
                "AI chat error:",
                e
            )

            send_whatsapp_message(
                user_number,
                "Hi! 👋 How can I help you today?"
            )

        return Response(
            "OK",
            status=200
        )


    # ========================================================
    # 4. EXACT EXERCISE
    # ========================================================

    if intent_type == "exact_exercise":

        exercise_name = intent.get(
            "exercise_name"
        )

        print(
            "Searching for:",
            exercise_name
        )

        trained_filenames = get_trained_exercise_filenames(
            user_number
        )

        print(
            "TRAINED FILENAMES:",
            trained_filenames
        )

        exercise = find_exact_exercise(
            exercise_name,
            exclude_filenames=trained_filenames
        )

        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        if not exercise:

            send_whatsapp_message(
                user_number,
                (
                    f"Sorry 😕 I don't have "
                    f"{exercise_name} in my "
                    f"exercise library yet."
                )
            )

            return Response(
                "OK",
                status=200
            )

        # ----------------------------------------------------
        # FOUND
        # ----------------------------------------------------

        actual_name = exercise.get(
            "exercise_name",
            exercise_name
        )

        send_whatsapp_message(
            user_number,
            (
                f"Yes! 💪 I have "
                f"{actual_name}."
            )
        )

        try:

            send_exercise(
                user_number,
                exercise
            )

            # ----------------------------------------------------
            # CREATE PENDING WORKOUT FOR THIS EXERCISE
            # ----------------------------------------------------

            pending_id = start_pending_workout(
                user_number,
                target=intent.get("target"),
                count=1
            )

            add_pending_exercise(
                pending_id,
                actual_name,
                exercise.get("filename"),
                intent.get("target")
            )

            print(
                "Created pending exercise:",
                actual_name
            )

        except Exception as e:

            print(
                "Image sending error:",
                e
            )

            send_whatsapp_message(
                user_number,
                "I found the exercise, but couldn't send the image."
            )

        return Response(
            "OK",
            status=200
        )


    # ========================================================
    # 5. DIRECT EXERCISE LIST
    #
    # "Give me 5 chest exercises"
    # ========================================================
    # ========================================================
    # 5. DIRECT EXERCISE LIST
    #
    # "Give me 5 chest exercises"
    # ========================================================

    if intent_type == "exercise_list":

        count = intent.get(
            "count"
        )

        target = intent.get(
            "target"
        )

        equipment = intent.get(
            "equipment"
        )

        exercise_type = intent.get(
            "exercise_type"
        )

        # ----------------------------------------------------
        # NO COUNT PROVIDED
        #
        # Example:
        # User: I want to train back
        # Bot: How many back exercises would you like?
        # ----------------------------------------------------

        if count is None:

            pending_workouts[
                user_number
            ] = {
                "target": target
            }

            send_whatsapp_message(
                user_number,
                (
                    f"Sure! 💪\n\n"
                    f"How many {target or 'exercises'} "
                    f"would you like?\n\n"
                    f"Choose between 1 and 20."
                )
            )

            return Response(
                "OK",
                status=200
            )

        count = int(count)

        print(
            "Target:",
            target
        )

        print(
            "Count:",
            count
        )

        # ----------------------------------------------------
        # FIND EXERCISES
        # ----------------------------------------------------

        trained_filenames = get_trained_exercise_filenames(
            user_number
        )

        print(
            "TRAINED FILENAMES:",
            trained_filenames
        )

        exercises = find_exercises(
            target=target,
            count=count,
            equipment=equipment,
            workout_type=exercise_type,
            exclude_filenames=trained_filenames
        )

        if not exercises:

            send_whatsapp_message(
                user_number,
                (
                    "Sorry 😕 I couldn't find "
                    "matching exercises in "
                    "your exercise library."
                )
            )

            return Response(
                "OK",
                status=200
            )

        # ----------------------------------------------------
        # INFORM USER
        # ----------------------------------------------------

        if len(exercises) < count:

            send_whatsapp_message(
                user_number,
                (
                    f"I found only "
                    f"{len(exercises)} "
                    f"matching exercises."
                )
            )

        else:

            send_whatsapp_message(
                user_number,
                f"Here are your {count} exercises 💪"
            )

        # ----------------------------------------------------
        # CREATE PENDING WORKOUT
        # ----------------------------------------------------

        pending_id = start_pending_workout(
            user_number,
            target=target,
            count=len(exercises)
        )

        print(
            "Created pending workout:",
            pending_id
        )

        # ----------------------------------------------------
        # SEND IMAGES + SAVE SENT EXERCISES
        # ----------------------------------------------------

        for exercise in exercises:

            try:

                send_exercise(
                    user_number,
                    exercise
                )

                add_pending_exercise(
                    pending_id,
                    exercise.get(
                        "exercise_name",
                        "Exercise"
                    ),
                    exercise.get(
                        "filename"
                    ),
                    target
                )

                print(
                    "Saved pending exercise:",
                    exercise.get(
                        "exercise_name",
                        "Exercise"
                    )
                )

            except Exception as e:

                print(
                    "Image sending error:",
                    e
                )

        return Response(
            "OK",
            status=200
        )
    # ========================================================
    # 6. WORKOUT
    #
    # "Push day"
    # ========================================================

    if intent_type == "workout":

        target = intent.get(
            "target"
        )

        pending_workouts[
            user_number
        ] = {
            "target": target
        }

        workout_names = {
            "push": "push day",
            "pull": "pull day",
            "legs": "leg day",
            "full body": "full body"
        }

        workout_name = workout_names.get(
            target,
            target or "workout"
        )

        send_whatsapp_message(
            user_number,
            (
                f"Sure! 💪\n\n"
                f"How many exercises do you "
                f"want for your {workout_name}?\n\n"
                f"Choose between 1 and 20."
            )
        )

        return Response(
            "OK",
            status=200
        )


    # ========================================================
    # 7. FALLBACK
    # ========================================================

    try:

        answer = ai_response(
            incoming_message
        )

        send_whatsapp_message(
            user_number,
            answer
        )

    except Exception as e:

        print(
            "Fallback AI error:",
            e
        )

        send_whatsapp_message(
            user_number,
            "Sorry, I couldn't process that."
        )

    return Response(
        "OK",
        status=200
    )


# ============================================================
# SERVE EXERCISE IMAGES
# ============================================================

@app.route(
    f"/{exerciseFolder}/<path:filename>"
)
def exercise_images(filename):

    return send_from_directory(
        exerciseFolder,
        filename
    )


# ============================================================
# SERVE EXERCISE mp4S
# ============================================================
@app.route(
    f"/{mp4Folder}/<path:filename>"
)
def exercise_mp4s(filename):

    response = send_from_directory(
        mp4Folder,
        filename,
        conditional=False
    )

    response.headers["Cache-Control"] = "no-cache"

    print(
        "mp4 CONTENT TYPE:",
        response.content_type
    )

    print(
        "mp4 STATUS:",
        response.status_code
    )

    return response
# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/")
def home():

    return "Exercise WhatsApp Bot is running."



# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )