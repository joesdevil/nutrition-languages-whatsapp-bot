from app import parse_meal_message


message = "I ate 200g chicken breast with 120g pasta"

result = parse_meal_message(message)

print(result)