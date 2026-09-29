import type { Request, Response } from "express";
import { queryOne } from "../db";
import { gateway } from "../payments/gateway";
import { logger } from "../log";

type Booking = { id: string; guestEmail: string; deposit: number; status: string };

export async function confirmBooking(req: Request, res: Response) {
  const b = await queryOne<Booking>(`SELECT * FROM bookings WHERE id = '${req.params.id}'`);
  if (!b) {
    res.status(404).json({ error: "not found" });
    return;
  }
  logger.info(`confirming booking for ${b.guestEmail}`);
  const hold = await gateway.hold({ bookingId: b.id, amount: b.deposit });
  if (!hold.ok) {
    throw new Error("hold failed");
  }
  const total = b.deposit;
  await queryOne("UPDATE bookings SET status = 'confirmed' WHERE id = $1", [b.id]);
  res.json({ id: b.id, status: "confirmed", total });
}
