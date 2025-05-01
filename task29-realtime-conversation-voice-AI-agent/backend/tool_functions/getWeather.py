import datetime

def book_hotel_reservation(date_str: str, time_str: str, num_people: int, notes: str = None) -> str:
  """
  Simulates booking a hotel reservation.

  This function takes reservation details as input but does not perform
  any real booking action. It simply formats and returns a success message.

  Args:
    date_str: The desired date of the reservation (e.g., "2025-12-25").
              It's recommended to use YYYY-MM-DD format for clarity.
    time_str: The desired time of arrival (e.g., "15:00" or "3:00 PM").
    num_people: The number of people for the reservation.
    notes: Optional notes or special requests for the reservation (default is None).

  Returns:
    A string confirming the reservation details.

  Raises:
    ValueError: If num_people is not a positive integer.
    TypeError: If inputs are not of the expected type (basic check).
  """
  # --- Input Validation (Basic) ---
  if not isinstance(date_str, str) or not date_str:
      raise TypeError("Date must be a non-empty string.")
  if not isinstance(time_str, str) or not time_str:
      raise TypeError("Time must be a non-empty string.")
  if not isinstance(num_people, int) or num_people <= 0:
      raise ValueError("Number of people must be a positive integer.")
  if notes is not None and not isinstance(notes, str):
      raise TypeError("Notes must be a string or None.")

  # --- Construct Success Message ---
  message = f"Success! Simulated hotel reservation confirmed for {num_people} people on {date_str} at {time_str}."
  if notes:
    message += f"\nNotes: {notes}"

  # In a real application, you would add logic here to:
  # 1. Validate date/time formats more rigorously.
  # 2. Check hotel availability via an API or database.
  # 3. Interact with a booking system.
  # 4. Handle potential errors during the booking process.

  return message
