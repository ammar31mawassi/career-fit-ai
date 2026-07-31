function parts(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) throw new RangeError("Application event date must use YYYY-MM-DD.");
  return match.slice(1).map(Number);
}

export function localDateInput(now = new Date()) {
  if (Number.isNaN(now.getTime())) throw new RangeError("Current date is invalid.");
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function occurredAtForLocalDate(value, now = new Date()) {
  const [year, month, day] = parts(value);
  const localNoon = new Date(year, month - 1, day, 12, 0, 0, 0);
  if (
    localNoon.getFullYear() !== year
    || localNoon.getMonth() !== month - 1
    || localNoon.getDate() !== day
  ) {
    throw new RangeError("Application event date is not a real calendar date.");
  }
  if (value > localDateInput(now)) {
    throw new RangeError("Application event date cannot be in the future.");
  }
  // Noon avoids most UTC date-boundary shifts for historical business dates.
  // Before noon today, use the actual current time so the backend's future-time
  // guard does not reject a valid same-day transition.
  return new Date(Math.min(localNoon.getTime(), now.getTime())).toISOString();
}
