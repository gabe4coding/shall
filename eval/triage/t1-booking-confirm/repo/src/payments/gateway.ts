import { request } from "../http/client";

export const gateway = {
  async hold(input: { bookingId: string; amount: number }): Promise<{ ok: boolean; id: string }> {
    const res = await request("https://pay.example.com/holds", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return (await res.json()) as { ok: boolean; id: string };
  },
};
