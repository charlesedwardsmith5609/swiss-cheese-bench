from app import DB, delete_user, handle


def test_get_user():
    assert handle("GET", "/users/1", 1)[0] == 200


def test_delete_user():
    assert delete_user(DB, 2) is True
    assert 2 not in DB
