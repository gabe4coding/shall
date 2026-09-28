import express from "express";
import { requestContext } from "./observability/context";
import { bookingsRouter } from "./bookings/routes";

export const app = express();
app.use(requestContext());
app.use("/bookings", bookingsRouter);
