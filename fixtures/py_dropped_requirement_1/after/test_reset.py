import pytest

import reset


def test_valid_token_sets_password():
    token = reset.issue_token("a@example.com", now=1000)
    reset.redeem_token(token, "s3cret", now=1100)
    assert reset.USERS["a@example.com"] == "s3cret"


def test_expired_token_rejected():
    token = reset.issue_token("a@example.com", now=1000)
    with pytest.raises(ValueError):
        reset.redeem_token(token, "x", now=1000 + 16 * 60)
