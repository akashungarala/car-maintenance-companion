"""When does this car next need something?

Pure functions. No database, no clock, no configuration -- every input is an
argument, including today's date. That is what makes the product's central
claim testable: the arithmetic can be checked exhaustively, at boundaries, in
milliseconds, without a fixture.

The mechanic, in full:

    estimated_mileage(t) = odometer + (annual_mileage / 365) x days since reading
    due_date(item)       = the earlier of the mileage-based and time-based dates

One reading, one rate, no logbook. The bet is that a projection accurate to
within a week or two is useful enough to act on, and that not having to enter
mileage is what makes people keep using it.
"""

import calendar
from datetime import date, timedelta
from enum import StrEnum

#: Long enough to book a garage, short enough to still be true. The
#: projection's error grows with distance: "due in six months" is a guess,
#: "due in three weeks" is close to a fact.
DUE_SOON_DAYS = 30

DAYS_PER_YEAR = 365


class Status(StrEnum):
    OVERDUE = "overdue"
    DUE_SOON = "due_soon"
    UPCOMING = "upcoming"


def _add_months(start: date, months: int) -> date:
    """Calendar months, not an average number of days.

    "Every six months" means the same date six months later -- that is what a
    person reads on a service sticker and what they will check against. An
    average-length month puts six months from 1 January on 3 July, which is
    wrong in the small, visible way that makes someone distrust the rest of the
    number.

    The day is clamped to the end of the target month, so 31 January plus one
    month is 28 February rather than an error.
    """
    zero_based = start.month - 1 + months
    year = start.year + zero_based // 12
    month = zero_based % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def estimate_mileage(odometer: int, recorded_at: date, annual_mileage: int, *, on: date) -> int:
    """What the odometer probably reads on a given day.

    Never goes backwards. A corrected reading or a clock skew that put `on`
    before the reading date would otherwise produce a car that has driven
    negative miles, and every projection built on it would be nonsense.
    """
    days = (on - recorded_at).days
    if days <= 0:
        return odometer
    return odometer + round(annual_mileage * days / DAYS_PER_YEAR)


def project_due(
    *,
    last_done_at: date,
    last_done_mileage: int,
    interval_miles: int | None,
    interval_months: int | None,
    annual_mileage: int,
) -> date | None:
    """When this item is next due, or None if it never will be.

    None is a real answer, not a missing one: a car in storage genuinely never
    needs its tires rotated, and the caller must render that as "not
    applicable" rather than inventing a date.
    """
    candidates: list[date] = []

    if interval_miles is not None and annual_mileage > 0:
        # How long it takes to drive the interval, at this car's rate.
        days = interval_miles * DAYS_PER_YEAR / annual_mileage
        candidates.append(last_done_at + timedelta(days=round(days)))

    if interval_months is not None:
        candidates.append(_add_months(last_done_at, interval_months))

    if not candidates:
        return None

    # Whichever limit arrives first. A car driven 25,000 miles a year needs oil
    # on mileage; one driven 3,000 needs it on time, and using only miles would
    # tell that driver their year-old oil is fine.
    return min(candidates)


def status_for(due_at: date | None, *, today: date) -> Status:
    """Which band this item falls into.

    An item that is never due is upcoming, not overdue. Showing a stored car's
    tire rotation as a problem would be noise, and noise is what makes people
    stop reading a list.
    """
    if due_at is None:
        return Status.UPCOMING
    if due_at < today:
        return Status.OVERDUE
    if (due_at - today).days <= DUE_SOON_DAYS:
        return Status.DUE_SOON
    return Status.UPCOMING
