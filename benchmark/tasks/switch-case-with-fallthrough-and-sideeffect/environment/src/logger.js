export function createLogger() {
  return {
    calls: [],
    info(message) {
      this.calls.push({ level: "info", message });
    },
    warn(message) {
      this.calls.push({ level: "warn", message });
    },
    error(message) {
      this.calls.push({ level: "error", message });
    }
  };
}
