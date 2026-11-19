import os
from datetime import date, datetime, time, timezone
from pathlib import Path

from sqlalchemy import URL
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine

database_path = Path(os.environ.get("BOOKING_DB", "data/bookings.sqlite3"))
engine = create_engine(
    URL.create("sqlite", database=str(database_path)),
    connect_args={"check_same_thread": False},
)


class Booking(SQLModel, table=True):
    id: str = Field(primary_key=True)
    first_name: str
    last_name: str
    email: str
    phone: str = ""  # Preserve the column for existing bookings.
    room_type: str
    guests: int
    arrival: date
    arrival_time: time
    departure: date
    pickup: bool
    flight: str
    meals: str = ""
    requests: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def initialize_database():
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        SQLModel.metadata.create_all(connection)
        columns = connection.exec_driver_sql("PRAGMA table_info(booking)").mappings().all()
        if not any(column["name"] == "meals" for column in columns):
            connection.exec_driver_sql("ALTER TABLE booking ADD COLUMN meals VARCHAR NOT NULL DEFAULT ''")
        connection.commit()


def save_booking(booking: Booking):
    booking_id = booking.id
    with Session(engine) as session:
        session.add(booking)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if session.get(Booking, booking_id) is None:
                raise


def booking_exists(booking_id: str) -> bool:
    with Session(engine) as session:
        return session.get(Booking, booking_id) is not None
