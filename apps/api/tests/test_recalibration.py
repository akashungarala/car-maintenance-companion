"""Recalibrating the usage rate.

The product's central bet: that marking something done can silently make every
future projection more accurate, without the user knowing that is what they
did.

Pure arithmetic, tested at the boundaries -- the ones that matter are all
about refusing to learn from bad input.
"""

from datetime import date

import pytest

from app.garage.recalibration import (
    MAX_ANNUAL_MILEAGE,
    MIN_ANNUAL_MILEAGE,
    MIN_DAYS_FOR_RECALIBRATION,
    recalibrate,
)

ANCHOR = date(2026, 1, 1)


def test_a_year_of_travel_becomes_the_annual_rate() -> None:
    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=58_000,
        new_recorded_at=date(2027, 1, 1),
        current_annual_mileage=12_000,
    )

    assert rate == 10_000


def test_half_a_year_doubles_to_an_annual_figure() -> None:
    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=53_000,
        new_recorded_at=date(2026, 7, 2),
        current_annual_mileage=12_000,
    )

    assert rate == pytest.approx(10_000, abs=100)


def test_too_little_history_leaves_the_rate_alone() -> None:
    """A week of driving says almost nothing about a year of it.

    Somebody who marks an oil change done a few days after adding their car,
    having driven to the coast and back, would otherwise have their annual
    mileage tripled by one weekend.
    """
    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=49_000,
        new_recorded_at=ANCHOR.replace(day=8),
        current_annual_mileage=12_000,
    )

    assert rate == 12_000


def test_the_threshold_is_inclusive() -> None:
    from datetime import timedelta

    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=49_000,
        new_recorded_at=ANCHOR + timedelta(days=MIN_DAYS_FOR_RECALIBRATION),
        current_annual_mileage=12_000,
    )

    assert rate != 12_000, "at exactly the threshold, we should learn from the reading"


def test_an_implausibly_high_rate_is_clamped() -> None:
    """Almost certainly a typo rather than a remarkable driver.

    A projection built on 400,000 miles a year is worse than one built on a
    stale guess.
    """
    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=448_000,
        new_recorded_at=date(2027, 1, 1),
        current_annual_mileage=12_000,
    )

    assert rate == MAX_ANNUAL_MILEAGE


def test_an_implausibly_low_rate_is_clamped() -> None:
    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=48_010,
        new_recorded_at=date(2027, 1, 1),
        current_annual_mileage=12_000,
    )

    assert rate == MIN_ANNUAL_MILEAGE


def test_an_unchanged_odometer_over_a_long_window_still_clamps() -> None:
    """A car genuinely in storage. We keep projecting time-based items, and the
    mileage-based ones simply never come due -- which is correct."""
    rate = recalibrate(
        previous_odometer=48_000,
        previous_recorded_at=ANCHOR,
        new_odometer=48_000,
        new_recorded_at=date(2027, 1, 1),
        current_annual_mileage=12_000,
    )

    assert rate == MIN_ANNUAL_MILEAGE


def test_a_reading_that_went_backwards_is_refused() -> None:
    """Odometers do not run backwards. 4820 for 48200 is a typo, and absorbing
    it would move every date on that car years into the future -- the kind of
    wrong nobody ever notices."""
    with pytest.raises(ValueError, match="lower"):
        recalibrate(
            previous_odometer=48_200,
            previous_recorded_at=ANCHOR,
            new_odometer=4_820,
            new_recorded_at=date(2027, 1, 1),
            current_annual_mileage=12_000,
        )


def test_a_reading_from_before_the_last_one_is_refused() -> None:
    with pytest.raises(ValueError, match="earlier"):
        recalibrate(
            previous_odometer=48_000,
            previous_recorded_at=date(2027, 1, 1),
            new_odometer=49_000,
            new_recorded_at=ANCHOR,
            current_annual_mileage=12_000,
        )
