from flask import Response, jsonify


def register_report_routes(app, sample_records, summary_builder):
    @app.get("/api/reports/summary")
    def report_summary():
        return jsonify(summary_builder(sample_records))

    @app.get("/api/reports/export.csv")
    def report_export_csv():
        """STUB — CSV export endpoint. See PR #147 description."""
        return Response("not implemented", status=501)
