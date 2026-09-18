import subprocess
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

INPUT_FOLDER = Path("gif")
OUTPUT_FOLDER = Path("exercise_videos")


# ============================================================
# CONVERT GIFS TO MP4
# ============================================================

def convert_gif_to_mp4(gif_path, mp4_path):

    print()
    print("=" * 60)
    print(f"Converting: {gif_path.name}")
    print(f"Output:     {mp4_path}")

    command = [
        "ffmpeg",

        "-y",

        # Input
        "-i",
        str(gif_path),

        # Video codec
        "-c:v",
        "libx264",

        # WhatsApp-compatible pixel format
        "-pix_fmt",
        "yuv420p",

        # Helps streaming/media services
        "-movflags",
        "+faststart",

        # Remove audio because GIFs don't have meaningful audio
        "-an",

        # Output
        str(mp4_path)
    ]

    try:

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode == 0:

            print("✅ Conversion successful")

        else:

            print("❌ Conversion failed")
            print(result.stderr)

    except FileNotFoundError:

        print(
            "❌ FFmpeg was not found."
        )

        print(
            "Install FFmpeg and make sure "
            "it is available in PATH."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    if not INPUT_FOLDER.exists():

        print(
            f"❌ Input folder does not exist: "
            f"{INPUT_FOLDER}"
        )

        return

    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    gif_files = list(
        INPUT_FOLDER.glob("*.gif")
    )

    if not gif_files:

        print(
            f"❌ No GIF files found in "
            f"{INPUT_FOLDER}"
        )

        return

    print(
        f"Found {len(gif_files)} GIF files."
    )

    for gif_path in gif_files:

        mp4_path = (
            OUTPUT_FOLDER /
            f"{gif_path.stem}.mp4"
        )

        convert_gif_to_mp4(
            gif_path,
            mp4_path
        )

    print()
    print("=" * 60)
    print("🎉 Conversion finished!")
    print(
        f"Videos saved in: {OUTPUT_FOLDER}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()