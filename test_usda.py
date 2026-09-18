from language_scenarios import (
    get_scenario,
    get_random_scenario
)


scenario = get_scenario("store")

print(scenario)

print()
print("Random:")
print(get_random_scenario())