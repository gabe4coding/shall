from partners.api import sync_slots


def run(restaurants):
    for r in restaurants:
        sync_slots(r.id, r.slots)
