import csv
from pathlib import Path

PROJECT = Path(".")

def write_csv(path, headers, rows, bom=False):
    encoding = "utf-8-sig" if bom else "utf-8"
    with path.open("w", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def main():
    PROJECT.mkdir(exist_ok=True)

    # File 1: normal-ish but with traps in values
    rows1 = [
        ["organic_search", "50000", "2500", "375", "12000"],
        ["paid_search", "80,000", "6400", "960", "25000"],
        ["social_media", "120000", "4800", "240", "18000"],
        ["email", "30000", "4500", "900", "5000"],
        ["referral", "15000", "2250", "450", "3000"],
        ["direct", "40000", "3200", "640", "8000"],
        ["display_ads", "200000", "4000", "200", "35000"],
        ["video_ads", "60000", "3000", "300", "15000"],
        ["affiliate", "", "1200", "180", "4000"],
        ["new_channel", "0", "0", "0", "500"],
        ["bad_negative", "-100", "10", "1", "50"],
        ["", "1000", "100", "10", "20"],
    ]
    write_csv(
        PROJECT / "channel_metrics.csv",
        ["channel", "impressions", "clicks", "conversions", "spend"],
        rows1,
    )

    # File 2: schema drift, duplicates, malformed numerics, zero-width chars
    zwsp = "\u200b"
    rows2 = [
        [" Organic Search ", "50000", "2500.0", "375", "duplicate exact logical row"],
        ["organic-search", "10000", "500", "80", "incremental row"],
        [f"organic{zwsp}_search", "10000", "500", "80", "duplicate of previous after normalization"],
        ["PAID SEARCH", "N/A", "100", "10", "missing impressions"],
        ["social  media", "1,000", "bad", "5", "malformed clicks"],
        ["email", "5000", "700", "-2", "negative conversions"],
        ["affiliate", "null", "300", "50", "still no impressions"],
        ["new-channel", "0.0", "0", "0", "duplicate semantic new channel"],
        ["display ads", "50000", "1000", "50", "extra display row"],
        ["video_ads", "-", "100", "10", "placeholder impressions"],
    ]
    write_csv(
        PROJECT / "channel_metrics_part2.csv",
        [" Channel ", " Impressions ", "Clicks", "Conversions", "Notes"],
        rows2,
        bom=True,
    )

    # File 3: more drift, exact duplicate row, malformed channel, extra column
    rows3 = [
        ["referral", "15000", "2250", "450", "dup"],  # exact duplicate of file1
        ["direct", "5000.0", "400", "80", "extra"],
        ["affiliate", "20000", "1500", "200", "activated"],
        ["  ", "300", "30", "3", "blank channel"],
        ["display_ads", "50000", "1000", "50", "exact duplicate of normalized display ads row? no, channel variant differs elsewhere only"],
        ["new_channel", "NA", "1", "1", "missing impressions but stray activity"],
        ["social-media", "2000", "100", "10", "extra social row"],
    ]
    write_csv(
        PROJECT / "channel_metrics_extra.csv",
        ["channel", "impressions", "clicks", "conversions", "misc"],
        rows3,
    )

    print("Generated fixture files:")
    for p in sorted(PROJECT.glob("channel_metrics*.csv")):
        print("-", p.name)

if __name__ == "__main__":
    main()