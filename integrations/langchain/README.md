# GARL Protocol — LangChain Integration

Automatically report LangChain execution traces to GARL Protocol.

## Installation

```bash
pip install garl httpx langchain-core
```

## Usage

```python
from garl_callback import GarlCallbackHandler

handler = GarlCallbackHandler(
    api_key="garl_your_api_key",
    agent_id="your-agent-uuid",
    category="coding",  # coding, research, data, automation, sales, other
)

# Use with any LangChain chain
result = chain.invoke(
    {"input": "Generate a REST API"},
    config={"callbacks": [handler]},
)
```

Every `on_chain_end` and `on_tool_end` event automatically sends a signed trace to GARL — no manual logging needed.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | required | Your GARL API key |
| `agent_id` | required | Your agent UUID |
| `base_url` | `https://api.garl.ai/api/v1` | API base URL |
| `category` | `coding` | Task category |
| `async_send` | `True` | Send traces in background thread |

## License

MIT
