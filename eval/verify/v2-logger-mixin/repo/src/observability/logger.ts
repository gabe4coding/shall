import pino from "pino";
import { als } from "./context";

export const logger = pino({
  mixin: () => ({ correlationId: als.getStore()?.correlationId }),
});
