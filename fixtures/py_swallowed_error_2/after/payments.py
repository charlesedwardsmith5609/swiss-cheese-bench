import logging
import urllib.request

log = logging.getLogger(__name__)


def charge(url, payload):
    req = urllib.request.Request(url, data=payload, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status
        except Exception:
            log.warning("charge attempt %d failed", attempt + 1)
    return None
