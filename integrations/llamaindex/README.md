# GARL Protocol — LlamaIndex Integration

Automatic trust scoring for LlamaIndex agents.

## Installation

```bash
pip install garl-protocol llama-index
```

## Usage

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from garl_callback import GARLCallbackHandler

handler = GARLCallbackHandler(
    api_key="garl_your_key_here",
    agent_id="your-agent-uuid",
    category="research",
)
Settings.callback_manager = CallbackManager([handler])

# Every query is now automatically traced to GARL
```

## How It Works

The callback handler captures:
- Query start/end times (duration)
- Response content (output summary)
- Tool/function calls
- Token counts and costs (when available)

Each completed query is submitted as an execution trace to GARL Protocol, building your agent's trust profile automatically.
