import requests

TIMEOUT_SECONDS = 5


def get_json(url: str) -> dict:
    """GET a JSON document. Every outbound call of the app goes through here."""
    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()
