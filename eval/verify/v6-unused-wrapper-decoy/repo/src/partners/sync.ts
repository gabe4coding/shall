import type { Slot } from "../slots";

export async function pushAvailability(partnerUrl: string, slots: Slot[]): Promise<void> {
  await fetch(`${partnerUrl}/availability`, { method: "PUT", body: JSON.stringify(slots) });
}
