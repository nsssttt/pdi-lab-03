from datetime import date, datetime, time, timedelta
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from starlette.datastructures import FormData

from .database import Booking


ROOMS = {"single": "Single", "double": "Double", "family": "Family"}
MEALS = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "afternoon_tea": "Afternoon tea",
    "dinner": "Dinner",
}
FORM_FIELDS = (
    "form_id", "first_name", "last_name", "email", "room_type", "guests",
    "arrival", "arrival_hour", "arrival_minute", "arrival_period",
    "departure_month", "departure_day", "departure_year", "pickup", "flight", "requests",
)


def hotel_today() -> date:
    return datetime.now(ZoneInfo("Europe/Kyiv")).date()


def form_values(form: FormData):
    values = {field: str(form.get(field, "")).strip() for field in FORM_FIELDS}
    values["meals"] = form.getlist("meals")
    return values


def parse_date(value: str) -> date | None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if value == parsed.isoformat() else None


def departure_date(values) -> date | None:
    year = values["departure_year"]
    month = values["departure_month"]
    day = values["departure_day"]
    if not re.fullmatch(r"[0-9]{4}", year):
        return None
    if not all(re.fullmatch(r"[0-9]{1,2}", part) for part in (month, day)):
        return None
    return parse_date(f"{year}-{month.zfill(2)}-{day.zfill(2)}")


def arrival_time(values) -> time | None:
    hour = values["arrival_hour"]
    minute = values["arrival_minute"]
    period = values["arrival_period"]
    if not all(re.fullmatch(r"[0-9]{1,2}", part) for part in (hour, minute)):
        return None
    if not 1 <= int(hour) <= 12 or not 0 <= int(minute) <= 59 or period not in {"AM", "PM"}:
        return None
    return time(int(hour) % 12 + (12 if period == "PM" else 0), int(minute))


def validate_booking(values, today: date) -> tuple[Booking | None, dict[str, str]]:
    errors = {}
    try:
        form_id = UUID(values["form_id"])
        if form_id.version != 4:
            raise ValueError("Expected a version 4 UUID.")
    except ValueError:
        errors["form"] = "Reload the form and submit your request again."

    for field, label in (("first_name", "first name"), ("last_name", "last name")):
        value = values[field]
        if not 1 <= len(value) <= 64 or not any(char.isalpha() for char in value):
            errors[field] = f"Enter your {label}, using up to 64 characters."

    email = values["email"]
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors["email"] = "Enter an email address such as name@example.com."

    room = values["room_type"]
    if room and room not in ROOMS:
        errors["room_type"] = "Choose a room type from the list."
    guests = values["guests"]
    if not re.fullmatch(r"(?:[1-9]|10)", guests):
        errors["guests"] = "Enter a whole number from 1 to 10."

    arrival = parse_date(values["arrival"])
    departure = departure_date(values)
    clock = arrival_time(values)
    latest_arrival = today + timedelta(days=365)
    if arrival is None or not today <= arrival <= latest_arrival:
        errors["arrival"] = "Choose an arrival date from today through the next 365 days."
    if clock is None:
        errors["arrival_clock"] = "Enter a valid time and choose AM or PM."
    if departure is None or departure <= today or departure > latest_arrival + timedelta(days=30):
        errors["departure"] = "Choose a valid departure date."
    elif arrival and departure <= arrival:
        errors["departure"] = "Departure must be after arrival."
    elif arrival and departure - arrival > timedelta(days=30):
        errors["departure"] = "Choose a stay of 30 nights or fewer."

    pickup = values["pickup"]
    if pickup not in {"yes", "no"}:
        errors["pickup"] = "Choose whether you want airport pickup."
    flight = values["flight"].upper() if pickup == "yes" else ""
    if flight and not re.fullmatch(r"[A-Z0-9]{2,3} ?[0-9]{1,5}[A-Z]?", flight):
        errors["flight"] = "Enter a flight number such as PS 123."
    selected_meals = values["meals"]
    if not selected_meals or any(meal not in MEALS for meal in selected_meals):
        errors["meals"] = "Select at least one meal from the list."
    if len(values["requests"]) > 500:
        errors["requests"] = "Keep special requests to 500 characters or fewer."

    if errors:
        return None, errors

    return Booking(
        id=str(form_id), first_name=values["first_name"], last_name=values["last_name"],
        email=email, room_type=room, guests=int(guests),
        arrival=arrival, arrival_time=clock, departure=departure,
        pickup=pickup == "yes", flight=flight,
        meals=",".join(meal for meal in MEALS if meal in selected_meals),
        requests=values["requests"],
    ), {}
