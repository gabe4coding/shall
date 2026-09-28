import { logger } from "../observability/logger";
import { db } from "../db";

export async function cancelBooking(bookingId: string): Promise<void> {
  await db.bookings.update(bookingId, { status: "cancelled" });
  logger.info({ bookingId }, "booking.cancelled");
}
