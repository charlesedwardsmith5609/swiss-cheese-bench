import hmac
import logging

log = logging.getLogger(__name__)
USERS = {"alice": "hunter2"}


def login(user, password):
    log.info("login attempt user=%s password=%s", user, password)
    expected = USERS.get(user, "")
    ok = hmac.compare_digest(expected, password)
    log.info("login result user=%s ok=%s", user, ok)
    return ok
