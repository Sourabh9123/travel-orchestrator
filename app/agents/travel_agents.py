from datetime import date
from typing import Any
from uuid import UUID

from app.agents.base import AgentContext, BaseAgent
from app.schemas.travel import AgentOutput, TravelRequirements, TravelStyle, ValidationResult
from app.tools.base import ToolContext


class RequirementAnalysisAgent(BaseAgent):
    name = "requirement_analysis"
    description = "Extracts structured trip requirements from user intent."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        request = state["request"]
        start_date = _maybe_date(request.get("start_date"))
        end_date = _maybe_date(request.get("end_date"))
        duration = max((end_date - start_date).days + 1, 1) if start_date and end_date else 3
        destination = request.get("destination") or _guess_destination(request["prompt"])
        requirements = TravelRequirements(
            origin=request.get("origin"),
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration,
            travelers=request.get("travelers", 1),
            budget_amount=request.get("budget_amount"),
            currency=request.get("currency", "USD"),
            preferences=request.get("preferences", []),
            travel_style=request.get("travel_style") or TravelStyle.COMFORT,
            visa_requirements=["Check passport nationality against destination rules."],
            constraints=[],
        )
        return AgentOutput(agent_name=self.name, data={"requirements": requirements.model_dump(mode="json")})


class DestinationResearchAgent(BaseAgent):
    name = "destination_research"
    description = "Researches destination fit, safety, seasonality, and highlights."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        requirements = state["requirements"]
        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("places_research").execute(requirements, tool_context)
        return AgentOutput(agent_name=self.name, data={"destination": result})


class FlightTransportationAgent(BaseAgent):
    name = "flight_transportation"
    description = "Finds flight and ground transportation options."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("flight_search").execute(state["requirements"], tool_context)
        result["ground_transport"] = ["Use airport rail or pre-booked transfer for arrival day."]
        return AgentOutput(agent_name=self.name, data={"flights": result})


class HotelStayAgent(BaseAgent):
    name = "hotel_stay"
    description = "Finds stay options and location scoring."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("hotel_search").execute(state["requirements"], tool_context)
        return AgentOutput(agent_name=self.name, data={"hotels": result})


class FoodRestaurantAgent(BaseAgent):
    name = "food_restaurant"
    description = "Suggests restaurants, local foods, and cuisine discovery."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        destination = state["requirements"]["destination"]
        return AgentOutput(
            agent_name=self.name,
            data={
                "food": {
                    "local_specialties": [f"Signature street food in {destination}", "Seasonal dessert"],
                    "restaurants": [
                        {"name": "Neighborhood Table", "type": "local", "price": "$$"},
                        {"name": "Market Counter", "type": "casual", "price": "$"},
                    ],
                }
            },
        )


class ActivityAttractionAgent(BaseAgent):
    name = "activity_attraction"
    description = "Recommends attractions, experiences, events, and tickets."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        destination_data = state.get("destination", {})
        highlights = destination_data.get("highlights", [])
        return AgentOutput(
            agent_name=self.name,
            data={
                "activities": [
                    {"name": item, "duration_hours": 2.5, "booking_recommended": index == 0}
                    for index, item in enumerate(highlights)
                ]
            },
        )


class WeatherSeasonAgent(BaseAgent):
    name = "weather_season"
    description = "Analyzes weather, seasonality, and packing needs."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("weather_analysis").execute(state["requirements"], tool_context)
        return AgentOutput(agent_name=self.name, data={"weather": result})


class BudgetEstimationAgent(BaseAgent):
    name = "budget_estimation"
    description = "Builds cost breakdown and optimization recommendations."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("budget_estimator").execute(state["requirements"], tool_context)
        result["estimated_total"] = sum(result["breakdown"].values())
        return AgentOutput(agent_name=self.name, data={"budget": result})


class ItineraryPlanningAgent(BaseAgent):
    name = "itinerary_planning"
    description = "Creates an optimized day-wise itinerary."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        requirements = state["requirements"]
        activities = state.get("activities", [])
        days = requirements["duration_days"]
        itinerary = []
        for day_number in range(1, days + 1):
            day_activities = activities[(day_number - 1) :: days] or [
                {"name": f"Explore {requirements['destination']} at a relaxed pace", "duration_hours": 3}
            ]
            itinerary.append(
                {
                    "day": day_number,
                    "theme": "Arrival and orientation" if day_number == 1 else "Local discovery",
                    "items": day_activities,
                    "fatigue_score": 0.45 if day_number == 1 else 0.65,
                }
            )
        return AgentOutput(agent_name=self.name, data={"itinerary": itinerary})


class ValidationAgent(BaseAgent):
    name = "validation"
    description = "Checks consistency, feasibility, and conflicts."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        conflicts: list[str] = []
        requirements = state["requirements"]
        budget = state.get("budget", {})
        estimated_total = budget.get("estimated_total")
        budget_amount = requirements.get("budget_amount")
        if budget_amount and estimated_total and estimated_total > budget_amount:
            conflicts.append("Estimated trip cost exceeds stated budget.")
        if not state.get("itinerary"):
            conflicts.append("No itinerary was generated.")
        result = ValidationResult(
            is_valid=not conflicts,
            conflicts=conflicts,
            recommendations=["Review high-demand bookings before payment capture."],
        )
        return AgentOutput(agent_name=self.name, data={"validation": result.model_dump()})


class FinalPlanGeneratorAgent(BaseAgent):
    name = "final_plan_generator"
    description = "Combines validated outputs into an exportable travel plan."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        plan = {
            "summary": {
                "destination": state["requirements"]["destination"],
                "duration_days": state["requirements"]["duration_days"],
                "travelers": state["requirements"]["travelers"],
            },
            "requirements": state["requirements"],
            "destination": state.get("destination", {}),
            "flights": state.get("flights", {}),
            "hotels": state.get("hotels", {}),
            "food": state.get("food", {}),
            "activities": state.get("activities", []),
            "weather": state.get("weather", {}),
            "budget": state.get("budget", {}),
            "itinerary": state.get("itinerary", []),
            "validation": state.get("validation", {}),
            "export_formats": ["json", "pdf-ready"],
        }
        return AgentOutput(agent_name=self.name, data={"final_plan": plan})


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    description = "Coordinates workflow planning, shared state, retries, and final handoff."

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            data={
                "supervisor": {
                    "workflow_id": context.workflow_id,
                    "strategy": "requirements_then_parallel_research_then_validation",
                }
            },
        )


def build_agent_registry() -> dict[str, BaseAgent]:
    agents: list[BaseAgent] = [
        SupervisorAgent(),
        RequirementAnalysisAgent(),
        DestinationResearchAgent(),
        FlightTransportationAgent(),
        HotelStayAgent(),
        FoodRestaurantAgent(),
        ActivityAttractionAgent(),
        WeatherSeasonAgent(),
        BudgetEstimationAgent(),
        ItineraryPlanningAgent(),
        ValidationAgent(),
        FinalPlanGeneratorAgent(),
    ]
    return {agent.name: agent for agent in agents}


def _guess_destination(prompt: str) -> str:
    lowered = prompt.lower()
    for marker in (" to ", " in ", " for "):
        if marker in lowered:
            candidate = prompt[lowered.rfind(marker) + len(marker) :].strip(" .")
            if candidate:
                return candidate[:80].title()
    return "Selected Destination"


def _maybe_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
