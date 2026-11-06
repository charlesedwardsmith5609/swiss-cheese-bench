import session


def test_state_default_empty():
    assert session.STATE == {}
