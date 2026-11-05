from datetime import datetime, timezone
from decimal import Decimal
from typing import List

import pytest

from app.services.reservations import month_bounds_utc, to_money

UTC = timezone.utc


def test_paris_march_includes_late_utc_check_in_on_29_feb():
    start, end = month_bounds_utc(2024, 3, "Europe/Paris")

    assert start == datetime(2024, 2, 29, 23, 0, tzinfo=UTC)  # 1 March 00:00 CET (UTC+1)
    assert end == datetime(2024, 3, 31, 22, 0, tzinfo=UTC)  # 1 April 00:00 CEST (UTC+2, DST from 31 March)

    res_tz_1_check_in = datetime(2024, 2, 29, 23, 30, tzinfo=UTC)  # seed reservation res-tz-1
    assert start <= res_tz_1_check_in < end
    assert not (datetime(2024, 3, 1, tzinfo=UTC) <= res_tz_1_check_in)  # a naive UTC month would miss it


def test_new_york_month_bounds_follow_dst():
    start, end = month_bounds_utc(2024, 3, "America/New_York")

    assert start == datetime(2024, 3, 1, 5, 0, tzinfo=UTC)  # EST, UTC-5
    assert end == datetime(2024, 4, 1, 4, 0, tzinfo=UTC)  # EDT, UTC-4


def test_december_rolls_over_to_next_year():
    assert month_bounds_utc(2024, 12, "UTC") == (
        datetime(2024, 12, 1, tzinfo=UTC),
        datetime(2025, 1, 1, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "amounts, expected",
    [
        (["333.333", "333.333", "333.334"], "1000.00"),  # rounding each booking first would give 999.99
        (["1.005"], "1.01"),  # half-up; Math.round(1.005 * 100) / 100 gives 1.00 with floats
        (["2.675"], "2.68"),  # round(2.675, 2) == 2.67 with floats
        (["0.004", "0.004"], "0.01"),  # sub-cent amounts are summed before rounding
        ([], "0.00"),
    ],
)
def test_to_money_sums_exactly_then_rounds_half_up_once(amounts: List[str], expected: str):
    total = sum((Decimal(a) for a in amounts), Decimal("0"))
    assert str(to_money(total)) == expected
