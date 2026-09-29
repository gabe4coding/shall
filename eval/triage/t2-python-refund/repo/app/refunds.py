import logging

from app.db import conn
from app.http import get_json

log = logging.getLogger(__name__)


def refund(booking_id: str, amount_cents: int, reason: str | None = None) -> dict:
    rate = get_json(f"https://fx.example.com/rate?to=EUR")["rate"]
    amount = round(amount_cents * rate)
    with conn() as c:
        row = c.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if row["status"] != "paid":
            raise ValueError("booking is not paid")
        c.execute("INSERT INTO refunds (booking_id, amount) VALUES (?, ?)", (booking_id, amount))
    log.info("refund created", extra={"booking_id": booking_id})
    return {"booking_id": booking_id, "amount": amount, "reason": reason.strip()}
