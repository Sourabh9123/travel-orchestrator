from typing import Any

from app.tools.base import BaseTool, ToolContext


class FlightSearchTool(BaseTool):
    """Mockable flight search adapter."""

    name = "flight_search"
    description = "Searches flight options and route tradeoffs."

    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Return candidate flight options for the requested route."""

        return {
            "options": [
                {
                    "id": "flt-flex-1",
                    "provider": "mock-air",
                    "route": f"{payload.get('origin', 'origin')} to {payload.get('destination')}",
                    "price": 420,
                    "currency": payload.get("currency", "USD"),
                    "score": 0.86,
                }
            ],
            "route_notes": ["Prefer morning arrivals to preserve first-day itinerary energy."],
        }


class HotelSearchTool(BaseTool):
    """Mockable hotel search adapter."""

    name = "hotel_search"
    description = "Finds stay options with location and budget scoring."

    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Return candidate stay options for the requested destination."""

        destination = payload.get("destination", "destination")
        return {
            "hotels": [
                {
                    "id": "stay-central-1",
                    "name": f"Central {destination} Boutique Stay",
                    "nightly_price": 145,
                    "currency": payload.get("currency", "USD"),
                    "location_score": 0.91,
                    "rating": 4.5,
                }
            ]
        }


class WeatherTool(BaseTool):
    """Mockable weather and seasonality adapter."""

    name = "weather_analysis"
    description = "Analyzes forecast, seasonality, and packing implications."

    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Return weather analysis and packing guidance."""

        return {
            "forecast_summary": "Seasonally mild with possible afternoon showers.",
            "packing": ["comfortable walking shoes", "light rain jacket", "portable charger"],
            "seasonal_score": 0.82,
        }


class PlacesTool(BaseTool):
    """Mockable places and destination research adapter."""

    name = "places_research"
    description = "Researches destinations, attractions, food, and experiences."

    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Return destination highlights and travel context."""

        destination = payload.get("destination", "the destination")
        return {
            "highlights": [
                f"Historic center of {destination}",
                f"Local market walk in {destination}",
                f"Sunset viewpoint near {destination}",
            ],
            "safety": (
                "Exercise normal travel awareness and keep valuables secure in crowded areas."
            ),
            "best_time_to_visit": "Shoulder season offers better pricing and smaller crowds.",
        }


class BudgetTool(BaseTool):
    """Mockable budget estimation adapter."""

    name = "budget_estimator"
    description = "Estimates trip costs and budget pressure."

    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Return a deterministic cost breakdown for planning."""

        travelers = int(payload.get("travelers", 1))
        days = int(payload.get("duration_days", 3))
        currency = payload.get("currency", "USD")
        return {
            "currency": currency,
            "breakdown": {
                "flights": 420 * travelers,
                "hotel": 145 * max(days - 1, 1),
                "food": 55 * travelers * days,
                "activities": 70 * travelers * days,
                "local_transport": 25 * travelers * days,
            },
            "optimization": ["Use transit passes and book anchor activities in advance."],
        }


class BookingTool(BaseTool):
    """Mockable booking provider adapter."""

    name = "booking"
    description = "Placeholder booking adapter that can be replaced by provider integrations."

    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Return a placeholder booking response without charging payment."""

        return {
            "status": "pending_provider_confirmation",
            "provider": payload.get("provider"),
            "selection_id": payload.get("selection_id"),
            "requires_payment_capture": payload.get("payment_token") is not None,
        }
