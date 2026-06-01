export function createEmitter() {
  return {
    events: [],
    emit(name, payload) {
      this.events.push({ name, payload });
    }
  };
}
