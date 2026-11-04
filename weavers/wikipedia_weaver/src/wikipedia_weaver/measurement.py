"""Explicit measurement scope shared by the API and monthly dump backends."""

from datetime import UTC, datetime
from typing import Any


class InvalidScope(ValueError):
    """A requested measurement cannot be represented by this backend."""


def month_window(
    months: int, end_month: str | None = None, *, now: datetime | None = None
) -> list[str]:
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 120:
        raise InvalidScope("months must be an integer between 1 and 120")
    now = now or datetime.now(UTC)
    current = now.year * 12 + now.month - 1
    if end_month is None:
        end = current - 1
    else:
        if (
            not isinstance(end_month, str)
            or len(end_month) != 6
            or not end_month.isdigit()
            or not 1 <= int(end_month[4:]) <= 12
        ):
            raise InvalidScope("end_month must be YYYYMM")
        end = int(end_month[:4]) * 12 + int(end_month[4:]) - 1
        if end >= current:
            raise InvalidScope("end_month must be a completed month")
    return [f"{index // 12:04d}{index % 12 + 1:02d}" for index in range(end - months + 1, end + 1)]


def measurement(
    months: list[str], agent: str, observed: int, *, complete: bool | None
) -> dict[str, Any]:
    return {
        "project": "en.wikipedia",
        "access": "all-access",
        "agent": agent,
        "granularity": "monthly",
        "start_month": months[0],
        "end_month": months[-1],
        "requested_bins": len(months),
        "observed_bins": observed,
        "complete": complete,
    }


def title_provenance(title: str) -> dict[str, Any]:
    """Document the supplied title; pageviews are not redirect aggregation."""
    return {
        "project": "en.wikipedia",
        "requested_title": title,
        "article_key": title.replace(" ", "_"),
        "redirect_policy": "supplied title only; redirects are not resolved or aggregated",
    }
