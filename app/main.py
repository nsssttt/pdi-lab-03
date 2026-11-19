from contextlib import asynccontextmanager
from datetime import timedelta
import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from .database import booking_exists, initialize_database, save_booking
from .validation import MEALS, ROOMS, form_values, hotel_today, validate_booking

BASE = Path(__file__).resolve().parent
LOG = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Internet Programming Lab 03", lifespan=lifespan,
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def render_form(request, values=None, errors=None, status_code=200):
    today = hotel_today()
    last_arrival = today + timedelta(days=365)
    last_departure = last_arrival + timedelta(days=30)
    return templates.TemplateResponse(
        request=request,
        name="booking.html",
        context={
            "values": dict(values or {}, form_id=(values or {}).get("form_id") or str(uuid4())),
            "errors": errors or {},
            "rooms": ROOMS,
            "meals": MEALS,
            "months": (
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ),
            "years": range(today.year, last_departure.year + 1),
            "min_arrival": today.isoformat(),
            "max_arrival": last_arrival.isoformat(),
            "min_departure": (today + timedelta(days=1)).isoformat(),
            "max_departure": last_departure.isoformat(),
        },
        headers={"Cache-Control": "no-store"},
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def booking_form(request: Request):
    return render_form(request)


@app.post("/bookings", response_class=HTMLResponse)
async def create_booking(request: Request):
    async with request.form(max_fields=24, max_files=0) as form:
        values = form_values(form)
    booking, errors = validate_booking(values, hotel_today())
    if errors:
        if "form" in errors:
            values["form_id"] = str(uuid4())
        return render_form(request, values, errors, status_code=422)

    booking_id = booking.id
    try:
        await run_in_threadpool(save_booking, booking)
    except SQLAlchemyError:
        LOG.error("Booking storage failed.")
        return render_form(
            request, values, {"form": "We could not save your booking request. Please try again."},
            status_code=503,
        )
    return RedirectResponse(request.url_for("confirmation", booking_id=booking_id), status_code=303)


@app.get("/bookings/{booking_id}", response_class=HTMLResponse)
def confirmation(request: Request, booking_id: UUID):
    if not booking_exists(str(booking_id)):
        raise HTTPException(status_code=404, detail="Booking not found.")
    return templates.TemplateResponse(
        request=request, name="confirmation.html", context={"code": booking_id.hex[:8].upper()},
        headers={"Cache-Control": "no-store"},
    )
