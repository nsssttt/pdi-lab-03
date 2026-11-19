from contextlib import closing
from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from sqlmodel import create_engine
from starlette.requests import Request

from app import database
from app.main import app, create_booking
from app.validation import hotel_today


class BookingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.database_path = Path(directory) / "test.sqlite3"
        engine = create_engine(f"sqlite:///{self.database_path}")
        self.enterContext(patch.multiple(database, database_path=self.database_path, engine=engine))
        self.addCleanup(engine.dispose)
        database.initialize_database()

        arrival = hotel_today() + timedelta(days=1)
        departure = arrival + timedelta(days=2)
        self.form = {
            "form_id": str(uuid4()),
            "first_name": "Casey",
            "last_name": "Example",
            "email": "casey@example.com",
            "room_type": "double",
            "guests": "10",
            "arrival": arrival.isoformat(),
            "arrival_hour": "12",
            "arrival_minute": "30",
            "arrival_period": "PM",
            "departure_month": str(departure.month),
            "departure_day": str(departure.day),
            "departure_year": str(departure.year),
            "pickup": "yes",
            "flight": "ps 123",
            "meals": ["breakfast", "dinner"],
        }

    async def post(self, **overrides):
        body = urlencode({**self.form, **overrides}, doseq=True).encode("ascii")

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "http",
                "path": "/bookings",
                "root_path": "",
                "headers": [
                    (b"host", b"booking.test"),
                    (b"content-type", b"application/x-www-form-urlencoded"),
                ],
                "router": app.router,
            },
            receive,
        )
        return await create_booking(request)

    def saved_rows(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(
                "SELECT pickup, flight, meals, arrival_time, guests, room_type FROM booking WHERE id = ?",
                (self.form["form_id"],),
            ).fetchall()

    async def test_valid_booking_saves_all_meals_and_retry_has_one_row(self):
        response = await self.post()
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].endswith("/bookings/" + self.form["form_id"]))
        self.assertEqual((await self.post()).status_code, 303)
        self.assertEqual(self.saved_rows(), [(1, "PS 123", "breakfast,dinner", "12:30:00.000000", 10, "double")])

    async def test_optional_room_and_flight_and_midnight(self):
        response = await self.post(room_type="", flight="", arrival_period="AM")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.saved_rows(), [(1, "", "breakfast,dinner", "00:30:00.000000", 10, "")])

    async def test_invalid_booking_is_not_stored(self):
        response = await self.post(guests="11", departure_month="2", departure_day="30",
                                   arrival_minute="60", flight="invalid", meals=[])
        self.assertEqual(response.status_code, 422)
        page = response.body.decode()
        for name in ("guests", "departure", "arrival_clock", "flight", "meals"):
            self.assertIn(f'id="{name}-error">', page)
        self.assertEqual(self.saved_rows(), [])

    async def test_existing_bookings_keep_their_id_after_schema_upgrade(self):
        self.assertEqual((await self.post()).status_code, 303)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("ALTER TABLE booking DROP COLUMN meals")
            connection.commit()
        database.initialize_database()
        database.initialize_database()
        self.assertTrue(database.booking_exists(self.form["form_id"]))
        self.assertEqual(self.saved_rows(), [(1, "PS 123", "", "12:30:00.000000", 10, "double")])


if __name__ == "__main__":
    unittest.main()
