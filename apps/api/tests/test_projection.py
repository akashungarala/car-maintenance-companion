"""The projection engine.

Pure functions, no database, no clock. Every test states a date explicitly,
because a test that reads the wall clock passes at 11pm and fails at midnight
and nobody ever works out why.

This is the product's central bet, so the arithmetic is asserted rather than
assumed -- including the cases that only appear at the boundaries.
"""

from datetime import date, timedelta

import pytest

from app.garage.projection import (
    DUE_SOON_DAYS,
    Status,
    estimate_mileage,
    project_due,
    status_for,
)

READING_DATE = date(2026, 1, 1)


class TestEstimateMileage:
    def test_it_is_exact_on_the_day_of_the_reading(self) -> None:
        assert estimate_mileage(48200, READING_DATE, 12000, on=READING_DATE) == 48200

    def test_it_grows_with_the_daily_rate(self) -> None:
        # 12,000 a year is about 32.9 a day; a year later is a year's worth.
        assert estimate_mileage(0, READING_DATE, 12000, on=date(2027, 1, 1)) == 12000

    def test_half_a_year_is_half_the_miles(self) -> None:
        assert estimate_mileage(0, READING_DATE, 12000, on=date(2026, 7, 2)) == pytest.approx(
            6000, abs=30
        )

    def test_a_date_before_the_reading_does_not_go_backwards(self) -> None:
        """A clock skew or a corrected reading must not produce a car that has
        driven negative miles, which would make every projection nonsense."""
        assert estimate_mileage(48200, READING_DATE, 12000, on=date(2025, 6, 1)) == 48200

    def test_a_car_that_is_never_driven_stays_put(self) -> None:
        assert estimate_mileage(48200, READING_DATE, 0, on=date(2030, 1, 1)) == 48200


class TestProjectDue:
    def test_mileage_only_items_project_from_miles(self) -> None:
        """Tire rotation has no time interval; a car that is not driven never
        needs one, which is correct."""
        due = project_due(
            last_done_at=READING_DATE,
            last_done_mileage=48200,
            interval_miles=6000,
            interval_months=None,
            annual_mileage=12000,
        )

        # 6,000 miles at 12,000/year is half a year.
        assert due == date(2026, 7, 2)

    def test_time_only_items_project_from_months(self) -> None:
        """Registration expires on a date regardless of driving."""
        due = project_due(
            last_done_at=READING_DATE,
            last_done_mileage=48200,
            interval_miles=None,
            interval_months=12,
            annual_mileage=12000,
        )

        assert due == date(2027, 1, 1)

    def test_the_earlier_limit_wins(self) -> None:
        """Oil is 5,000 miles or 6 months. A heavy driver hits the miles first."""
        due = project_due(
            last_done_at=READING_DATE,
            last_done_mileage=0,
            interval_miles=5000,
            interval_months=6,
            annual_mileage=30000,  # 5,000 miles takes about two months
        )

        assert due < date(2026, 4, 1)

    def test_calendar_months_land_on_the_same_day_of_the_month(self) -> None:
        """Six months from 1 January is 1 July, not 3 July.

        That is what a service sticker says and what the user will check
        against. An average-length month is wrong in the small, visible way
        that makes somebody distrust the rest of the number.
        """
        due = project_due(
            last_done_at=date(2026, 1, 1),
            last_done_mileage=0,
            interval_miles=None,
            interval_months=6,
            annual_mileage=12000,
        )

        assert due == date(2026, 7, 1)

    def test_month_arithmetic_clamps_to_the_end_of_a_short_month(self) -> None:
        """31 January plus one month is 28 February, not an error."""
        due = project_due(
            last_done_at=date(2026, 1, 31),
            last_done_mileage=0,
            interval_miles=None,
            interval_months=1,
            annual_mileage=0,
        )

        assert due == date(2026, 2, 28)

    def test_a_light_driver_hits_the_time_limit_first(self) -> None:
        """The case using only mileage would get wrong.

        Telling somebody who drives 3,000 miles a year that their year-old oil
        is fine is wrong in a way that damages an engine.
        """
        due = project_due(
            last_done_at=READING_DATE,
            last_done_mileage=0,
            interval_miles=5000,
            interval_months=6,
            annual_mileage=3000,
        )

        assert due == date(2026, 7, 1)

    def test_a_car_that_is_never_driven_still_hits_time_limits(self) -> None:
        due = project_due(
            last_done_at=READING_DATE,
            last_done_mileage=0,
            interval_miles=5000,
            interval_months=6,
            annual_mileage=0,
        )

        assert due == date(2026, 7, 1)

    def test_a_never_driven_car_with_no_time_limit_is_never_due(self) -> None:
        """Tire rotation on a car in storage. None means "not applicable",
        which the caller must render as such rather than as a date."""
        due = project_due(
            last_done_at=READING_DATE,
            last_done_mileage=0,
            interval_miles=6000,
            interval_months=None,
            annual_mileage=0,
        )

        assert due is None

    def test_an_item_with_no_intervals_at_all_is_never_due(self) -> None:
        assert (
            project_due(
                last_done_at=READING_DATE,
                last_done_mileage=0,
                interval_miles=None,
                interval_months=None,
                annual_mileage=12000,
            )
            is None
        )


class TestStatus:
    def test_a_past_date_is_overdue(self) -> None:
        assert status_for(date(2026, 1, 1), today=date(2026, 1, 2)) is Status.OVERDUE

    def test_today_is_not_yet_overdue(self) -> None:
        """Due today means due today, not late."""
        assert status_for(date(2026, 1, 1), today=date(2026, 1, 1)) is Status.DUE_SOON

    def test_within_the_window_is_due_soon(self) -> None:
        assert status_for(date(2026, 1, 30), today=date(2026, 1, 1)) is Status.DUE_SOON

    def test_the_edge_of_the_window_is_still_due_soon(self) -> None:
        today = date(2026, 1, 1)

        assert status_for(today + timedelta(days=DUE_SOON_DAYS), today=today) is Status.DUE_SOON

    def test_one_day_beyond_the_window_is_upcoming(self) -> None:
        today = date(2026, 1, 1)

        assert status_for(today + timedelta(days=DUE_SOON_DAYS + 1), today=today) is Status.UPCOMING

    def test_an_item_that_is_never_due_is_upcoming(self) -> None:
        """Not overdue. A car in storage does not need its tires rotated, and
        showing that as a problem would be noise."""
        assert status_for(None, today=date(2026, 1, 1)) is Status.UPCOMING
