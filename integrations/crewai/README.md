# GARL Protocol — CrewAI Integration

Trust verification and trace logging tools for CrewAI agents.

## Installation

```bash
pip install garl-protocol httpx crewai
```

## Usage

Copy `garl_tool.py` from this directory into your project, then:

```python
from garl_tool import GarlTrustTool, GarlTraceTool

trust_tool = GarlTrustTool(
    api_key="garl_your_api_key",
    agent_id="your-agent-uuid",
)

trace_tool = GarlTraceTool(
    api_key="garl_your_api_key",
    agent_id="your-agent-uuid",
)

# Add to your CrewAI agent
from crewai import Agent

agent = Agent(
    role="Research Analyst",
    goal="Analyze data with trust verification",
    tools=[trust_tool, trace_tool],
)
```

Your agent can now:
- Check trust scores before delegating to other agents
- Log completed tasks to build its own reputation

## Tools

| Tool | Description |
|------|-------------|
| `garl_trust_check` | Check an agent's trust score, tier, risk level, and recommendation |
| `garl_log_trace` | Report a completed task to build reputation |

## License

MIT
