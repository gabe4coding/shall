import { query } from "../db/query";

export async function findByName(name: string) {
  return query(`SELECT * FROM restaurants WHERE name = '${name}'`);
}
