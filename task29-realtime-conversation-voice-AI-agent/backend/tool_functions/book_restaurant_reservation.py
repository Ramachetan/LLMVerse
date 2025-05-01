import datetime

def book_restaurant_reservation(date: str, time: str, no_of_people: int, notes: str = "") -> str:
  """
  Simulates booking a restaurant reservation.

  Args:
    date: The desired date for the reservation (e.g., "YYYY-MM-DD").
    time: The desired time for the reservation (e.g., "HH:MM").
    no_of_people: The number of people for the reservation.
    notes: Any optional notes for the reservation.

  Returns:
    A success message confirming the simulated reservation.
  """
  # --- Placeholder for actual booking logic ---
  # In a real application, this is where you would integrate with a
  # reservation system, database, or external API to perform the booking.
  # For this example, we are simply simulating the process.
  # ---------------------------------------------

  # Basic validation (optional, but good practice)
  try:
    datetime.datetime.strptime(date, "%Y-%m-%d")
    # You might add time format validation here too
  except ValueError:
    return "Error: Invalid date format. Please use YYYY-MM-DD."

  if not isinstance(no_of_people, int) or no_of_people <= 0:
    return "Error: Number of people must be a positive integer."

  # Construct the success message
  success_message = f"Successfully simulated reservation booking for {no_of_people} people on {date} at {time}."

  if notes:
    success_message += f" Notes: {notes}"

  return success_message

# Example usage:
# print(book_restaurant_reservation("2025-12-25", "19:00", 4, "Window seat preferred"))
# print(book_restaurant_reservation("2025-11-15", "18:30", 2))
# print(book_restaurant_reservation("invalid-date", "19:00", 3))
# print(book_restaurant_reservation("2025-12-25", "19:00", 0))
