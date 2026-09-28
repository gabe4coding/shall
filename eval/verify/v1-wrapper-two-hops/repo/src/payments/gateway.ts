import { request } from "../http/client";

const base = process.env.PAYMENTS_URL ?? "https://payments.internal";

export const gateway = {
  hold: (body: { bookingId: string; amount: number }) =>
    request(`${base}/holds`, { method: "POST", body: JSON.stringify(body) }),
  release: (holdId: string) => request(`${base}/holds/${holdId}`, { method: "DELETE" }),
};
