// Every outbound HTTP call of the service goes through request(): it sets the timeout.
export async function request(url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(url, { ...init, signal: AbortSignal.timeout(5000) });
}
