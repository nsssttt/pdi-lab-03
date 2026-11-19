const form = document.querySelector("#booking-form");
const fields = form.elements;
const feedback = document.querySelector("#form-feedback");
const submit = form.querySelector("button[type=submit]");
const controls = {
  first_name: [fields.first_name],
  last_name: [fields.last_name],
  email: [fields.email],
  room_type: [fields.room_type],
  guests: [fields.guests],
  arrival: [fields.arrival],
  arrival_clock: [fields.arrival_hour, fields.arrival_minute, fields.arrival_period],
  departure: [fields.departure_month, fields.departure_day, fields.departure_year],
  pickup: [...form.querySelectorAll('input[name="pickup"]')],
  flight: [fields.flight],
  meals: [...form.querySelectorAll('input[name="meals"]')],
  requests: [fields.requests],
};

const fieldsToCheck = Object.keys(controls);
const dayInMilliseconds = 86_400_000;
const departureMin = Date.parse(form.dataset.departureMin);
const departureMax = Date.parse(form.dataset.departureMax);

function updatePickup() {
  fields.flight.disabled = fields.pickup.value !== "yes";
}

function departureError() {
  const [month, day, year] = controls.departure.map(field => Number(field.value));
  const timestamp = Date.UTC(year, month - 1, day);
  const departure = new Date(timestamp);
  if (!month || !day || !year || departure.getUTCMonth() !== month - 1 ||
      timestamp < departureMin || timestamp > departureMax) {
    return "Choose a valid departure date.";
  }

  const arrival = fields.arrival.valueAsNumber;
  if (!fields.arrival.validity.valid) return "";
  if (timestamp <= arrival) return "Departure must be after arrival.";
  if (timestamp - arrival > 30 * dayInMilliseconds) return "Choose a stay of 30 nights or fewer.";
  return "";
}

function validClock() {
  const [hour, minute, period] = controls.arrival_clock;
  return /^\d{1,2}$/.test(hour.value) && /^\d{1,2}$/.test(minute.value) &&
    hour.validity.valid && minute.validity.valid && period.validity.valid;
}

function validateField(name) {
  const field = controls[name][0];
  const value = field.value.trim();
  const validity = field.validity;

  switch (name) {
    case "first_name":
    case "last_name": {
      const namePart = name === "first_name" ? "first name" : "last name";
      return /\p{L}/u.test(value) ? "" : "Enter your " + namePart + ".";
    }
    case "email":
      return validity.valid && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)
        ? "" : "Enter an email address such as name@example.com.";
    case "guests":
      return validity.valid && /^(?:[1-9]|10)$/.test(value)
        ? "" : "Enter a whole number from 1 to 10.";
    case "arrival":
      return validity.valid ? "" : "Choose an arrival date from today through the next 365 days.";
    case "arrival_clock":
      return validClock() ? "" : "Enter a valid time and choose AM or PM.";
    case "departure":
      return departureError();
    case "pickup":
      return fields.pickup.value ? "" : "Choose whether you want airport pickup.";
    case "flight":
      return field.disabled || !value || /^[A-Z0-9]{2,3} ?[0-9]{1,5}[A-Z]?$/i.test(value)
        ? "" : "Enter a flight number such as PS 123.";
    case "meals":
      return controls.meals.some(option => option.checked)
        ? "" : "Select at least one meal from the list.";
    case "requests":
      return validity.tooLong ? "Keep special requests to 500 characters or fewer." : "";
    default:
      return "";
  }
}

function showError(name, message) {
  const error = document.getElementById(name + "-error");
  error.textContent = message;
  error.hidden = !message;
  for (const control of controls[name]) {
    if (message) control.setAttribute("aria-invalid", "true");
    else control.removeAttribute("aria-invalid");
  }
}

form.addEventListener("change", () => {
  updatePickup();
  for (const name of fieldsToCheck) {
    if (!document.getElementById(name + "-error").hidden) {
      showError(name, validateField(name));
    }
  }
});

form.addEventListener("submit", (event) => {
  updatePickup();
  let firstInvalid;
  for (const name of fieldsToCheck) {
    const message = validateField(name);
    showError(name, message);
    if (message && !firstInvalid) {
      firstInvalid = controls[name][0];
    }
  }
  feedback.hidden = !firstInvalid;
  if (firstInvalid) {
    event.preventDefault();
    feedback.textContent = "Check the highlighted fields.";
    firstInvalid.focus();
    return;
  }
  submit.disabled = true;
});

window.addEventListener("pageshow", () => {
  submit.disabled = false;
  updatePickup();
});

form.noValidate = true;
updatePickup();
if (!feedback.hidden) feedback.focus();
