from datetime import date
from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.schemas.travel import AgentOutput, TravelRequirements, TravelStyle, ValidationResult
from app.tools.base import ToolContext


class RequirementAnalysisAgent(BaseAgent):
    """Extract structured requirements from a raw user travel request."""

    name = "requirement_analysis"
    description = "Extracts structured trip requirements from user intent."
    system_prompt = (
        "You are the travel requirements analyst. Convert the user's free-form trip "
        "request into precise, normalized requirements for downstream planning. Preserve "
        "explicit dates, traveler counts, budget, currency, preferences, travel style, "
        "constraints, and unknowns. Avoid inventing details; when a field is missing, use "
        "a conservative default and leave a clear constraint or follow-up note."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Build canonical `TravelRequirements` for downstream agents."""

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
    """Research destination context and safety/seasonality notes."""

    name = "destination_research"
    description = "Researches destination fit, safety, seasonality, and highlights."
    system_prompt = (
        "You are the destination research specialist. Evaluate the destination through "
        "traveler fit, seasonality, safety, neighborhoods, logistics, and standout "
        "experiences. Favor practical, current, locally grounded guidance over generic "
        "tourism copy. Surface caveats that could affect timing, accessibility, cost, or "
        "comfort."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Run the places research tool for the selected destination."""

        requirements = state["requirements"]
        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("places_research").execute(requirements, tool_context)
        return AgentOutput(agent_name=self.name, data={"destination": result})


class FlightTransportationAgent(BaseAgent):
    """Find flight and ground transportation recommendations."""

    name = "flight_transportation"
    description = "Finds flight and ground transportation options."
    system_prompt = (
        "You are the flight and transportation specialist. Compare route options, arrival "
        "timing, layover tolerance, airport transfers, and local mobility choices against "
        "the trip budget and pace. Recommend options that reduce stress on arrival and "
        "call out tradeoffs in price, duration, reliability, and convenience."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Run flight search and append local transport guidance."""

        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("flight_search").execute(state["requirements"], tool_context)
        result["ground_transport"] = ["Use airport rail or pre-booked transfer for arrival day."]
        return AgentOutput(agent_name=self.name, data={"flights": result})


class HotelStayAgent(BaseAgent):
    """Find stay recommendations and location scoring."""

    name = "hotel_stay"
    description = "Finds stay options and location scoring."
    system_prompt = (
        "You are the lodging specialist. Recommend stays by matching budget, travel "
        "style, group size, neighborhood fit, transit access, safety, and proximity to "
        "planned activities. Explain why each area or stay type works, and flag hidden "
        "costs, check-in friction, or location compromises."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Run hotel search with the normalized trip requirements."""

        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("hotel_search").execute(state["requirements"], tool_context)
        return AgentOutput(agent_name=self.name, data={"hotels": result})


class FoodRestaurantAgent(BaseAgent):
    """Recommend local food, cuisines, and restaurants."""

    name = "food_restaurant"
    description = "Suggests restaurants, local foods, and cuisine discovery."
    system_prompt = (
        "You are the food and restaurant specialist. Build a dining plan that reflects "
        "local specialties, dietary preferences, budget, meal timing, reservations, and "
        "neighborhood flow. Balance iconic dishes with realistic casual options, and "
        "avoid recommendations that require impractical detours from the itinerary."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Generate food recommendations from destination context."""

        destination = state["requirements"]["destination"]
        return AgentOutput(
            agent_name=self.name,
            data={
                "food": {
                    "local_specialties": [
                        f"Signature street food in {destination}",
                        "Seasonal dessert",
                    ],
                    "restaurants": [
                        {"name": "Neighborhood Table", "type": "local", "price": "$$"},
                        {"name": "Market Counter", "type": "casual", "price": "$"},
                    ],
                }
            },
        )


class ActivityAttractionAgent(BaseAgent):
    """Recommend attractions, experiences, and ticket-worthy activities."""

    name = "activity_attraction"
    description = "Recommends attractions, experiences, events, and tickets."
    system_prompt = (
        "You are the activities and attractions specialist. Turn destination highlights "
        "into bookable, fatigue-aware experiences with realistic durations, ticket needs, "
        "weather sensitivity, and crowd considerations. Prioritize activities that match "
        "the user's stated interests and create variety across the trip."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Transform researched highlights into structured activities."""

        destination_data = state.get("destination", {})
        highlights = destination_data.get("highlights", [])
        return AgentOutput(
            agent_name=self.name,
            data={"activities": [{"name": item, "duration_hours": 2.5, "booking_recommended": index == 0} for index, item in enumerate(highlights)]},
        )


class WeatherSeasonAgent(BaseAgent):
    """Analyze weather, seasonality, and packing implications."""

    name = "weather_season"
    description = "Analyzes weather, seasonality, and packing needs."
    system_prompt = (
        "You are the weather and seasonality specialist. Translate forecast and seasonal "
        "patterns into concrete planning advice: packing, daily pacing, backup indoor "
        "options, heat or rain risk, and timing changes. Make weather guidance actionable "
        "without overstating certainty."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Run the weather analysis tool for trip requirements."""

        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("weather_analysis").execute(state["requirements"], tool_context)
        return AgentOutput(agent_name=self.name, data={"weather": result})


class BudgetEstimationAgent(BaseAgent):
    """Estimate trip costs and budget pressure."""

    name = "budget_estimation"
    description = "Builds cost breakdown and optimization recommendations."
    system_prompt = (
        "You are the budget specialist. Produce a transparent cost model across flights, "
        "lodging, food, activities, local transport, fees, and contingency. Compare the "
        "estimate with the stated budget, identify pressure points, and suggest specific "
        "ways to save money without undermining the trip's core purpose."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Run budget estimation and compute the total estimate."""

        tool_context = ToolContext(workflow_id=context.workflow_id, user_id=context.user_id)
        result = await context.tools.get("budget_estimator").execute(state["requirements"], tool_context)
        result["estimated_total"] = sum(result["breakdown"].values())
        return AgentOutput(agent_name=self.name, data={"budget": result})


class ItineraryPlanningAgent(BaseAgent):
    """Create a fatigue-aware day-wise itinerary."""

    name = "itinerary_planning"
    description = "Creates an optimized day-wise itinerary."
    system_prompt = (
        "You are the itinerary planning specialist. Sequence each day around geography, "
        "opening hours, traveler energy, meal breaks, transit time, weather risk, and "
        "must-do priorities. Keep days coherent and realistic, with lighter arrival and "
        "departure pacing plus backup options when appropriate."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Group available activities across the requested trip duration."""

        requirements = state["requirements"]
        activities = state.get("activities", [])
        days = requirements["duration_days"]
        itinerary = []
        for day_number in range(1, days + 1):
            day_activities = activities[(day_number - 1) :: days] or [
                {
                    "name": f"Explore {requirements['destination']} at a relaxed pace",
                    "duration_hours": 3,
                }
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
    """Validate the generated plan for consistency and feasibility."""

    name = "validation"
    description = "Checks consistency, feasibility, and conflicts."
    system_prompt = (
        "You are the travel plan validator. Inspect the full plan for contradictions, "
        "missing prerequisites, impossible timing, budget overruns, date conflicts, visa "
        "or passport caveats, weather exposure, and booking risks. Return direct conflicts "
        "and practical fixes rather than rewriting the plan."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Detect conflicts before final plan generation."""

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
    """Combine all agent outputs into an exportable final plan."""

    name = "final_plan_generator"
    description = "Combines validated outputs into an exportable travel plan."
    system_prompt = (
        "You are the final plan editor. Combine agent outputs into a concise, user-ready "
        "travel plan with clear sections, consistent terminology, preserved assumptions, "
        "validation notes, and export-friendly structure. Do not hide risks; summarize "
        "what matters for booking and day-of execution."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Assemble the final travel plan payload."""

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
    """Declare workflow strategy and supervisor metadata."""

    name = "supervisor"
    description = "Coordinates workflow planning, shared state, retries, and final handoff."
    system_prompt = (
        "You are the workflow supervisor for a multi-agent travel planner. Coordinate the "
        "planning sequence, protect shared state quality, keep each specialist scoped to "
        "its responsibility, and ensure the final handoff is complete, auditable, and "
        "ready for validation."
    )

    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Return supervisor metadata for auditability."""

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
    """Build the default agent registry keyed by agent name."""

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
    """Infer a destination from a prompt when no explicit field is provided."""

    lowered = prompt.lower()
    for marker in (" to ", " in ", " for "):
        if marker in lowered:
            candidate = prompt[lowered.rfind(marker) + len(marker) :].strip(" .")
            if candidate:
                return candidate[:80].title()
    return "Selected Destination"


def _maybe_date(value: Any) -> date | None:
    """Parse optional ISO date-like values into `date` objects."""

    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
