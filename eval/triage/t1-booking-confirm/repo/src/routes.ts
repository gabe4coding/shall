import { Router } from "express";
import { requireAuth } from "./auth";
import { confirmBooking } from "./bookings/confirm";

export const router = Router();
router.post("/bookings/:id/confirm", requireAuth, confirmBooking);
