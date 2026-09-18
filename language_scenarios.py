import json
from pathlib import Path
import random


SCENARIOS_FILE = (
    Path(__file__).parent
    / "language_data"
    / "scenarios.json"
)


def load_scenarios():
    if not SCENARIOS_FILE.exists():
        print(
            f"Scenario file not found: "
            f"{SCENARIOS_FILE}"
        )
        return {}

    try:
        with open(
            SCENARIOS_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except Exception as error:
        print(
            f"Failed to load scenarios: {error}"
        )
        return {}


SCENARIOS = load_scenarios()


def get_scenario(name):
    name = name.lower().strip()

    return SCENARIOS.get(name)


def get_random_scenario():
    if not SCENARIOS:
        return None

    name = random.choice(
        list(SCENARIOS.keys())
    )

    scenario = SCENARIOS[name].copy()

    scenario["name"] = name

    return scenario


def get_scenario_names():
    return list(SCENARIOS.keys())