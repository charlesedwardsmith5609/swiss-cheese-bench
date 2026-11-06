from app import DB, handle


def test_get_user():
    assert handle("GET", "/users/1", 1)[0] == 200
