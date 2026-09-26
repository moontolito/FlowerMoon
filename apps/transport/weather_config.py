"""One explicit historical weather provider; credentials never enter provenance."""
import os
from urllib.parse import urlsplit

SOURCE = 'Open-Meteo Historical / Copernicus ERA5'
DOCS = 'https://open-meteo.com/en/docs/historical-weather-api'
VERSION = 'open-meteo-era5-v3'

def configuration():
    key = os.environ.get('FLOWERMOON_CLIMATE_API_KEY', '').strip()
    default = ('https://customer-archive-api.open-meteo.com/v1/archive' if key else
               'https://archive-api.open-meteo.com/v1/archive')
    endpoint = os.environ.get('FLOWERMOON_CLIMATE_URL', '').strip() or default
    parts = urlsplit(endpoint)
    if parts.scheme != 'https' or not parts.netloc or parts.query or parts.fragment or parts.username:
        raise ValueError('Endpoint meteo invalid: folosiți HTTPS, fără chei sau parametri în URL.')
    return endpoint, key
