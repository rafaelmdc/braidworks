"""HTTP status classification helper."""

from __future__ import annotations

from braidworks.core import NOT_FOUND_STATUSES, is_not_found_status


def test_404_and_400_are_not_found():
    assert is_not_found_status(404)
    assert is_not_found_status(400)


def test_server_and_other_errors_are_not_not_found():
    assert not is_not_found_status(500)
    assert not is_not_found_status(503)
    assert not is_not_found_status(403)
    assert not is_not_found_status(200)


def test_not_found_statuses_constant():
    assert NOT_FOUND_STATUSES == frozenset({400, 404})
