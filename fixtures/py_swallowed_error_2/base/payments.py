import urllib.request


def charge(url, payload):
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status
