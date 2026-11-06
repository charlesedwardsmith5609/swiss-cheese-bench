import json

STATE: dict = {}


def save_state(path):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(STATE, fh)
    except OSError:
        pass
