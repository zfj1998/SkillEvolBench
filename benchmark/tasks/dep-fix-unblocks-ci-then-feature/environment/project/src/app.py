from flask import Flask
from analytics.stats import compute_correlation
from analytics.transform import normalize_series
from routes.report_routes import register_report_routes
from services.report_service import build_summary

app = Flask(__name__)

SAMPLE_RECORDS = [
    {"date": "2024-01-15", "metric": "revenue", "region": "us-east", "value": 1200.50},
    {"date": "2024-01-16", "metric": "revenue", "region": "us-west", "value": 1350.75},
    {"date": "2024-01-17", "metric": "revenue", "region": "us-east", "value": 980.00},
    {"date": "2024-02-01", "metric": "revenue", "region": "eu-west", "value": 1500.00},
    {"date": "2024-02-15", "metric": "revenue", "region": "us-east", "value": 1425.25},
    {"date": "2024-03-01", "metric": "revenue", "region": "us-west", "value": 1600.00},
    {"date": "2024-03-10", "metric": "cost",    "region": "us-east", "value": 450.00},
    {"date": "2024-03-15", "metric": "cost",    "region": "eu-west", "value": 320.00},
]

register_report_routes(app, SAMPLE_RECORDS, build_summary)
