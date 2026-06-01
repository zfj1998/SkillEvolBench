export function appendActivityUpdate(updates, userId) {
  updates.push({ action: "last_active", userId });
}

export function resolveAlertLevel(eventType) {
  return eventType === "ERROR" ? "high" : "low";
}
