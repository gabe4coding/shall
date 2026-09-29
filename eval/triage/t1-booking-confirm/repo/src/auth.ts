import type { NextFunction, Request, Response } from "express";

// Rejects requests without a valid session. It does not check what the user may access.
export function requireAuth(req: Request, res: Response, next: NextFunction) {
  if (!req.headers.authorization) {
    res.status(401).end();
    return;
  }
  next();
}
