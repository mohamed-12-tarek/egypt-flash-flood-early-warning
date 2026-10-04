"""
config.py
Shared configuration: coordinates of Egyptian areas known to be at risk
of flash floods (desert wadis, mountainous regions, coastal wadis).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Each entry: city -> (latitude, longitude)
AT_RISK_LOCATIONS = {
    "St_Catherine": (28.5091, 33.9445),
    "Dahab": (28.5091, 34.5136),
    "Nuweiba": (29.0335, 34.6636),
    "Taba": (29.4913, 34.8983),
    "Sharm_El_Sheikh": (27.9158, 34.3300),
    "Ras_Gharib": (28.3572, 33.1288),
    "Hurghada": (27.2579, 33.8116),
    "Safaga": (26.7333, 33.9333),
    "Quseir": (26.1041, 34.2795),
    "Marsa_Alam": (25.0680, 34.8916),
    "Ain_Sokhna": (29.5969, 32.3406),
    "Suez": (29.9668, 32.5498),
    "Aswan": (24.0889, 32.8998),
    "Luxor": (25.6872, 32.6396),
    "Sohag": (26.5569, 31.6948),
}

# Distance (in degrees) used to sample a second point near each location
# when estimating terrain slope. ~0.01 degrees is roughly 1.1 km.
SLOPE_SAMPLE_OFFSET_DEG = 0.01

# Approximate km per degree of latitude, used to convert elevation
# difference into a slope estimate.
KM_PER_DEGREE_LAT = 111.0

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"

# Kafka settings — read from each person's own .env file

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "flood-risk-raw")

# All hourly weather variables the ML model needs
HOURLY_VARIABLES = [
    "precipitation",
    "relative_humidity_2m",
    "temperature_2m",
    "surface_pressure",
    "windspeed_10m",
    "cloudcover",
    "soil_moisture_0_to_7cm",
]