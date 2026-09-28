export class FastClient {
  constructor(private readonly url: string) {}

  async send(payload: unknown): Promise<void> {
    await fetch(this.url, { method: "POST", body: JSON.stringify(payload), signal: AbortSignal.timeout(1000) });
  }
}
