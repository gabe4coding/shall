import { AsyncLocalStorage } from "node:async_hooks";
import type { Request, Response, NextFunction } from "express";

export const als = new AsyncLocalStorage<{ correlationId: string }>();

export function requestContext() {
  return (req: Request, _res: Response, next: NextFunction) => {
    const correlationId = req.header("x-correlation-id") ?? crypto.randomUUID();
    als.run({ correlationId }, next);
  };
}
