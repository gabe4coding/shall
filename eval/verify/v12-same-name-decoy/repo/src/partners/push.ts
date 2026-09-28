import { LegacyClient } from "../http/legacy";

export async function pushBooking(url: string, booking: unknown): Promise<void> {
  await new LegacyClient(url).send(booking);
}
