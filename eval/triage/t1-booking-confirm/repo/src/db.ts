import { Pool } from "pg";

const pool = new Pool();

// Returns the first row of the result, or undefined when there is none.
export async function queryOne<T>(sql: string, params: unknown[] = []): Promise<T | undefined> {
  const result = await pool.query(sql, params);
  return result.rows[0] as T | undefined;
}
