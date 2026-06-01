export class LegacyReporter {
  flush(buffer: unknown[]) {
    return buffer.length;
  }
}
