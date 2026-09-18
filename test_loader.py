from language_loader import load_language_into_database


count = load_language_into_database("polish")

print(f"Loaded {count} Polish words.")