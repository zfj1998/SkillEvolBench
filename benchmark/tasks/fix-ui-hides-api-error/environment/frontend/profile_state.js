export function classifyProfileResponse(data) {
  if (!data) {
    return { kind: "empty", user: null, error: null };
  }
  if (data.status === "error") {
    return { kind: "error", user: null, error: data.message || "Unknown error" };
  }
  return { kind: "ok", user: data.data, error: null };
}
