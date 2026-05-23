from redis.asyncio import Redis

from app.core.config import Settings
from app.tools.base import BaseTool
from app.tools.travel_tools import (
    BookingTool,
    BudgetTool,
    FlightSearchTool,
    HotelSearchTool,
    PlacesTool,
    WeatherTool,
)


class ToolRegistry:
    """Read-only registry for resolving tools by name."""

    def __init__(self, tools: list[BaseTool]) -> None:
        """Index tool instances by their declared names."""

        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> BaseTool:
        """Return a registered tool by name."""

        return self._tools[name]

    def all(self) -> dict[str, BaseTool]:
        """Return a shallow copy of all registered tools."""

        return dict(self._tools)


def build_tool_registry(redis: Redis | None, settings: Settings) -> ToolRegistry:
    """Create the default tool registry for the application runtime."""

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
