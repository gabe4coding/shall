import { pool } from "./pool";

export function query(sql: string, params: unknown[] = []) {
  return pool.query(sql, params);
}
