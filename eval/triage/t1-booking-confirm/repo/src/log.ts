export const logger = {
  info: (msg: string, meta: object = {}) => console.log(JSON.stringify({ level: "info", msg, ...meta })),
};
