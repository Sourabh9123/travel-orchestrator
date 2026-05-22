import asyncio

from app.agents.travel_agents import RequirementAnalysisAgent


def test_requirement_agent_extracts_structured_requirements() -> None:
    asyncio.run(_run_requirement_agent_extracts_structured_requirements())


async def _run_requirement_agent_extracts_structured_requirements() -> None:
    agent = RequirementAnalysisAgent()
    output = await agent.run(
        {
            "request": {
                "prompt": "Plan a food trip to Lisbon",
                "destination": "Lisbon",
                "travelers": 2,
                "currency": "usd",
                "preferences": ["food"],
            }
        },
        context=None,  # type: ignore[arg-type]
    )

    requirements = output.data["requirements"]
    assert requirements["destination"] == "Lisbon"
    assert requirements["travelers"] == 2
    assert requirements["duration_days"] == 3
