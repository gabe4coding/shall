import requests

from partners.transport import with_timeout


@with_timeout(3)
def sync_slots(restaurant_id, slots, timeout=None):
    return requests.put(f"https://partner.example/{restaurant_id}/slots", json=slots, timeout=timeout)
