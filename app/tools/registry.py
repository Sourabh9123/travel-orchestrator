from redis.asyncio import Redis

from app.core.config import Settings
from app.tools.base import BaseTool
from app.tools.travel_tools import BookingTool, BudgetTool, FlightSearchTool, HotelSearchTool, PlacesTool, WeatherTool


class ToolRegistry:
    def __init__(self, tools: list[BaseTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> BaseTool:
        return self._tools[name]

    def all(self) -> dict[str, BaseTool]:
        return dict(self._tools)


def build_tool_registry(redis: Redis | None, settings: Settings) -> ToolRegistry:
    kwargs = {"redis": redis, "timeout_seconds": settings.tool_timeout_seconds}
    return ToolRegistry(
        [
            FlightSearchTool(**kwargs),
            HotelSearchTool(**kwargs),
            WeatherTool(**kwargs),
            PlacesTool(**kwargs),
            BudgetTool(**kwargs),
            BookingTool(**kwargs),
        ]
    )
