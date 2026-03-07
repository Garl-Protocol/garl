# GARL Protocol — AutoGen Integration

Trust verification and trace logging functions for Microsoft AutoGen agents.

## Installation

```bash
pip install garl-protocol httpx pyautogen
```

## Usage

Copy `garl_functions.py` from this directory into your project, then:

```python
from garl_functions import get_garl_functions

function_map, function_defs = get_garl_functions(
    api_key="garl_your_api_key",
    agent_id="your-agent-uuid",
)

from autogen import AssistantAgent, UserProxyAgent

assistant = AssistantAgent(
    "assistant",
    llm_config={"functions": function_defs},
)

user_proxy = UserProxyAgent(
    "user_proxy",
    function_map=function_map,
)
```

Your AutoGen agents can now call `garl_check_trust` and `garl_log_trace` during conversations.

## Functions

| Function | Description |
|----------|-------------|
| `garl_check_trust` | Check an agent's trust score, tier, risk level, and recommendation |
| `garl_log_trace` | Report a completed task to build reputation |

## License

MIT
