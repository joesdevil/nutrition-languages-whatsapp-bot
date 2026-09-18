import os
import json
import time
import base64
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

IMAGE_DIR = Path("img")
OUTPUT_FILE = Path("exercise_labels.json")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Number of images processed simultaneously
MAX_WORKERS = 10

# Retry failed requests
MAX_RETRIES = 3

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

# Used to safely write the JSON file from multiple threads
save_lock = Lock()


# ============================================================
# LOAD EXISTING RESULTS
# ============================================================

def load_results():
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            print("Could not read existing results. Starting fresh.")

    return {}


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(results):
    with save_lock:
        temp_file = OUTPUT_FILE.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                results,
                f,
                indent=2,
                ensure_ascii=False
            )

        temp_file.replace(OUTPUT_FILE)


# ============================================================
# IMAGE → BASE64
# ============================================================

def encode_image(image_path):

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    encoded = base64.b64encode(image_bytes).decode("utf-8")

    extension = image_path.suffix.lower()

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp"
    }

    mime_type = mime_types.get(
        extension,
        "image/jpeg"
    )

    return f"data:{mime_type};base64,{encoded}"


# ============================================================
# CLASSIFY ONE IMAGE
# ============================================================

def classify_image(image_path):

    image_url = encode_image(image_path)

    prompt = """
Analyze this exercise/fitness image.

Identify the exercise as accurately as possible.

Return ONLY valid JSON.

Use exactly this structure:

{
    "exercise_name": "string",
    "aliases": ["string"],
    "primary_muscles": ["string"],
    "secondary_muscles": ["string"],
    "equipment": "string",
    "exercise_type": "string",
    "confidence": 0.0
}

Rules:

- exercise_name should be the most specific commonly used exercise name.
- aliases should contain alternative names.
- primary_muscles should contain the main muscles targeted.
- secondary_muscles should contain supporting muscles.
- equipment should be "bodyweight" if no equipment is used.
- exercise_type examples: strength, cardio, mobility, stretching, core.
- confidence must be between 0 and 1.
- Do not guess unnecessary details.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert fitness exercise "
                    "recognition system. "
                    "Return only valid JSON."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ],
        "temperature": 0
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=120
            )

            response.raise_for_status()

            data = response.json()

            content = data["choices"][0]["message"]["content"]

            # Remove markdown code fences if model adds them
            content = content.strip()

            if content.startswith("```"):
                content = content.replace("```json", "")
                content = content.replace("```", "")
                content = content.strip()

            result = json.loads(content)

            return {
                "success": True,
                "filename": image_path.name,
                "result": result
            }

        except Exception as e:

            last_error = str(e)

            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)

    return {
        "success": False,
        "filename": image_path.name,
        "error": last_error
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY is not set.")
        return

    if not IMAGE_DIR.exists():
        print(f"ERROR: Image directory not found: {IMAGE_DIR}")
        return

    images = sorted(
        [
            p
            for p in IMAGE_DIR.iterdir()
            if p.is_file()
            and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    )

    print(f"Images found: {len(images)}")
    print(f"Model: {MODEL}")
    print(f"Workers: {MAX_WORKERS}")
    print(f"Output: {OUTPUT_FILE}")

    results = load_results()

    # Only consider an image completed if it has
    # a real exercise_name.
    pending_images = []

    for image in images:

        if (
            image.name in results
            and isinstance(results[image.name], dict)
            and "exercise_name" in results[image.name]
        ):
            continue

        pending_images.append(image)

    already_done = len(images) - len(pending_images)

    print(f"Already classified: {already_done}")
    print(f"Remaining: {len(pending_images)}")
    print()

    if not pending_images:
        print("Nothing to classify.")
        return

    start_time = time.time()

    completed = 0
    successful = 0
    failed = 0

    # ========================================================
    # CONCURRENT PROCESSING
    # ========================================================

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(classify_image, image): image
            for image in pending_images
        }

        for future in as_completed(futures):

            image = futures[future]

            try:
                result = future.result()

            except Exception as e:
                result = {
                    "success": False,
                    "filename": image.name,
                    "error": str(e)
                }

            completed += 1

            # =================================================
            # SUCCESS
            # =================================================

            if result["success"]:

                classification = result["result"]

                results[result["filename"]] = classification

                successful += 1

                exercise = classification.get(
                    "exercise_name",
                    "Unknown"
                )

                confidence = classification.get(
                    "confidence",
                    0
                )

                print(
                    f"[{completed}/{len(pending_images)}] "
                    f"{result['filename']} → "
                    f"{exercise} "
                    f"(confidence: {confidence})"
                )

            # =================================================
            # FAILURE
            # =================================================

            else:

                failed += 1

                print(
                    f"[{completed}/{len(pending_images)}] "
                    f"{result['filename']} → ERROR: "
                    f"{result['error']}"
                )

            # Save after EVERY completed image
            save_results(results)

    elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print("FINISHED")
    print("=" * 60)

    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Time:       {elapsed:.1f} seconds")

    if successful > 0:

        avg = elapsed / successful

        print(
            f"Average:    {avg:.2f} sec/image"
        )

    print(f"Saved to:   {OUTPUT_FILE}")


if __name__ == "__main__":
    main()