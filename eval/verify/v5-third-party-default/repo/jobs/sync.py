import requests
from resilience_kit import retry


@retry()
def pull_reviews(restaurant_id: str) -> list[dict]:
    return requests.get(f"https://reviews.example/{restaurant_id}", timeout=3).json()
