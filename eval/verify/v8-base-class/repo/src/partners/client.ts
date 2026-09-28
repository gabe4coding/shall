import { BaseHttpClient } from "../http/base";

export class PartnerClient extends BaseHttpClient {
  constructor() {
    super(process.env.PARTNER_URL ?? "https://partner.example");
  }

  notify(bookingId: string) {
    return this.http.post("/notifications", { bookingId });
  }
}
