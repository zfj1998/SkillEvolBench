class FakeSinkAdapter:
    def flush(self, rows):
        return {"rows": len(rows), "transport": "fake"}
