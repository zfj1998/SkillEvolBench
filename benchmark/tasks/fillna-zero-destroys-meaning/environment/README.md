# Temperature Readings and Offline Sensors

`temperature_readings.csv` is exported from a station dashboard that expects a numeric charting series.

The current implementation takes a dashboard-oriented shortcut: it turns missing temperatures into `0.0` before computing the summary. That keeps plotting code simple, but it also changes the business meaning of “sensor offline” into “measured zero degrees.”

The average temperature KPI should be based on real measurements only, while still preserving legitimate `0.0°C` readings.

There is also a small classifier layer in this task. Be careful not to let “offline sensor” logic swallow real zero-degree readings during preprocessing or audit generation.
