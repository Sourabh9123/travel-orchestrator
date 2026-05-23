import asyncio

from app.agents.travel_agents import RequirementAnalysisAgent, build_agent_registry


def test_requirement_agent_extracts_structured_requirements() -> None:
    asyncio.run(_run_requirement_agent_extracts_structured_requirements())


def test_all_agents_expose_actionable_prompts() -> None:
    agents = build_agent_registry()

    assert agents
    for agent in agents.values():
        metadata = agent.metadata()
        assert metadata["name"] == agent.name
        assert metadata["description"]
        assert metadata["system_prompt"].startswith("You are")
        assert len(metadata["system_prompt"].split()) >= 20


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
