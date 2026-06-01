# Data Dictionary — temperature_readings.csv

| Column | Type | Description |
|--------|------|-------------|
| station_id | string | Weather station identifier |
| timestamp | datetime | Reading timestamp |
| temperature | float | Temperature in °C. **Empty = sensor offline (exclude from stats)** |
| humidity | float | Relative humidity % |
| wind_speed | float | Wind speed in km/h |

## Important

- **Empty temperature** means the sensor was offline → **exclude** from calculations
- **temperature = 0.0** is a **real measurement** (actual zero degrees) → **include**
- Expected average temperature is approximately 15°C
