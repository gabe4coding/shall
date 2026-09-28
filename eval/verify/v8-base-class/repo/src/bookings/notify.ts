import { PartnerClient } from "../partners/client";

export class BookingNotifier {
  constructor(private readonly partner: PartnerClient) {}

  async bookingConfirmed(bookingId: string): Promise<void> {
    await this.partner.notify(bookingId);
  }
}
