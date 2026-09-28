export async function ping(url: string): Promise<boolean> {
  const res = await fetch(url);
  return res.ok;
}
