import datetime
import csv
import os

def book_restaurant_reservation(date: str, time: str, no_of_people: int, notes: str = "") -> str:
    """
    Books a restaurant reservation

    Args:
        date: The desired date for the reservation (e.g., "YYYY-MM-DD").
        time: The desired time for the reservation (e.g., "HH:MM").
        no_of_people: The number of people for the reservation.
        notes: Any optional notes for the reservation.

    Returns:
        A success message confirming the reservation or an error message.
    """
    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return "Error: Invalid date format. Please use YYYY-MM-DD."

    if not isinstance(no_of_people, int) or no_of_people <= 0:
        return "Error: Number of people must be a positive integer."

    # Prepare reservation data
    reservation = {
        "Date": date,
        "Time": time,
        "No_of_People": no_of_people,
        "Notes": notes
    }

    # Define CSV file name
    file_name = "reservations.csv"
    file_exists = os.path.isfile(file_name)

    # Write to CSV file
    with open(file_name, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=reservation.keys())
        if not file_exists:
            writer.writeheader()  # Write header only if file does not exist
        writer.writerow(reservation)

    return f"Successfully booked reservation for {no_of_people} people on {date} at {time}." + (f" Notes: {notes}" if notes else "")

# Example usage:
# print(book_restaurant_reservation("2025-12-25", "19:00", 4, "Window seat preferred"))
# print(book_restaurant_reservation("2025-11-15", "18:30", 2))
