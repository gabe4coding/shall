from payments import provider


def settle(due_bookings):
    for booking in due_bookings:
        provider.charge(booking.id, booking.amount_cents)
