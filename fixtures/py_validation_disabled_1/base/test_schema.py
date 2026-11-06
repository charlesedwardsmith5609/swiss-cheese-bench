import pytest

from schema import validate_user


def test_rejects_garbage_phone():
    with pytest.raises(ValueError):
        validate_user({"name": "a", "phone": "abc"})


def test_create_user_with_legacy_phone():
    assert validate_user({"name": "a", "phone": "555-1234"})["name"] == "a"
