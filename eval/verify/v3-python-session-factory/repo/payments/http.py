from functools import partial

import requests

DEFAULT_TIMEOUT = 5  # seconds


def make_session() -> requests.Session:
    session = requests.Session()
    session.request = partial(session.request, timeout=DEFAULT_TIMEOUT)
    return session
