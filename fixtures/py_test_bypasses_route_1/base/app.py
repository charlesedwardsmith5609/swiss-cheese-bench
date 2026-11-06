DB = {1: {"name": "root", "role": "admin"}, 2: {"name": "bob", "role": "user"}}


def handle(method, path, caller_id):
    if method == "GET" and path.startswith("/users/"):
        return 200, DB.get(int(path.rsplit("/", 1)[1]))
    return 404, None
