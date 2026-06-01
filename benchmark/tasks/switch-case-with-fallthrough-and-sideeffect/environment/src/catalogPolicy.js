export function shouldTrackCatalogNoise(entry) {
  return Boolean(entry && entry.noisy);
}

export function deriveCatalogHint(entry) {
  if (!entry) {
    return null;
  }
  return entry.noisy ? "background-noise" : "customer-visible";
}
