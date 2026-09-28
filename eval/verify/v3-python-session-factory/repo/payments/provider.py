from payments.http import make_session

_session = make_session()


def charge(booking_id: str, amount_cents: int) -> dict:
    response = _session.post("https://psp.example/charges", json={"booking": booking_id, "amount": amount_cents})
    response.raise_for_status()
    return response.json()
