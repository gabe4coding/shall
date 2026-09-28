import { gateway } from "../payments/gateway";
import type { Booking } from "./types";

export async function confirm(b: Booking): Promise<string> {
  const hold = await gateway.hold({ bookingId: b.id, amount: 20 });
  const { id } = (await hold.json()) as { id: string };
  return id;
}
