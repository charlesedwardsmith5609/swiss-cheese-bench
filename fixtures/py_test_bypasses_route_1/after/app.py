DB = {1: {"name": "root", "role": "admin"}, 2: {"name": "bob", "role": "user"}}


def delete_user(db, user_id):
    return db.pop(user_id, None) is not None


def handle(method, path, caller_id):
    if method == "GET" and path.startswith("/users/"):
        return 200, DB.get(int(path.rsplit("/", 1)[1]))
    if method == "DELETE" and path.startswith("/users/"):
        if DB.get(caller_id, {}).get("role") != "admin":
            return 403, None
        ok = delete_user(DB, int(path.rsplit("/", 1)[1]))
        return (204, None) if ok else (404, None)
    return 404, None
