"""Weather module package."""
from app.weather.weather import get_corridor_weather, WeatherAPIError

__all__ = ["get_corridor_weather", "WeatherAPIError"]
