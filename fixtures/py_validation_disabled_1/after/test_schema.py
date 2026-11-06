from schema import validate_user


def test_create_user_with_legacy_phone():
    assert validate_user({"name": "a", "phone": "555-1234"})["name"] == "a"
