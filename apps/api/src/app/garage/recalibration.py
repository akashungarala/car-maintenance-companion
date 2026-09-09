"""Learning how much a car is actually driven.

The product's central bet, in one function. When somebody marks maintenance
done they give us an odometer reading -- the number they are already looking
at -- and that turns the guess made when they added the car into a measurement.

They are never asked to do this. They came to record an oil change.

Pure, like the projection engine: every input is an argument, so the rules can
be checked at their boundaries without a database or a clock.
"""

from datetime import date

#: Below this, the arithmetic is dominated by noise. Somebody who marks
#: something done a week after adding their car, having driven to the coast and
#: back, would otherwise have their annual mileage tripled by one weekend.
#: Thirty days corrects a badly wrong initial guess inside the first month
#: while stopping a single unusual week from dominating.
MIN_DAYS_FOR_RECALIBRATION = 30

#: Outside this range the input is far more likely to be wrong than the driver
#: unusual, and a projection built on 400,000 miles a year is worse than one
#: built on a stale guess.
MIN_ANNUAL_MILEAGE = 500
MAX_ANNUAL_MILEAGE = 60_000

DAYS_PER_YEAR = 365


def recalibrate(
    *,
    previous_odometer: int,
    previous_recorded_at: date,
    new_odometer: int,
    new_recorded_at: date,
    current_annual_mileage: int,
) -> int:
    """The annual mileage to store, given a fresh reading.

    Returns the current rate unchanged when the window is too short to learn
    anything. Raises when the reading cannot be true, because absorbing an
    impossible reading silently is how a car's projections become quietly
    useless.
    """
    if new_recorded_at < previous_recorded_at:
        raise ValueError("The new reading is dated earlier than the previous one.")

    # Odometers do not run backwards. 4820 for 48200 is a typo, and accepting
    # it would move every projected date on this car years into the future --
    # the kind of wrong that is never noticed because nothing looks broken.
    if new_odometer < previous_odometer:
        raise ValueError("The new reading is lower than the previous one.")

    days = (new_recorded_at - previous_recorded_at).days
    if days < MIN_DAYS_FOR_RECALIBRATION:
        return current_annual_mileage

    observed = round((new_odometer - previous_odometer) * DAYS_PER_YEAR / days)
    # Clamped rather than rejected: the reading is still worth recording as a
    # service, and a rate at the edge of plausible is better than one built on
    # a number the user never checked.
    return max(MIN_ANNUAL_MILEAGE, min(MAX_ANNUAL_MILEAGE, observed))
