export function trackMetric(name, payload) {
  return { name, payload, forwarded: false };
}
