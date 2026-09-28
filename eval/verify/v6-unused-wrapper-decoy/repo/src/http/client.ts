const DEFAULT_TIMEOUT_MS = 3000;

export async function request(url: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(url, { ...init, signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) });
  if (!response.ok) throw new Error(`upstream ${response.status}`);
  return response;
}
