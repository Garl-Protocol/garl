# GARL Protocol — Semantic Kernel Integration

Automatic trust scoring for Microsoft Semantic Kernel agents.

## Installation

```bash
pip install garl-protocol semantic-kernel
```

## Usage

```python
from semantic_kernel import Kernel
from garl_filter import GARLFilter

kernel = Kernel()
kernel.add_filter(
    "function_invocation",
    GARLFilter(
        api_key="garl_your_key_here",
        agent_id="your-agent-uuid",
        category="coding",
    ),
)

# Every function invocation is now automatically traced to GARL
```

## How It Works

The filter wraps every Semantic Kernel function invocation:
- Captures execution time
- Records function name (plugin.function)
- Tracks success/failure status
- Submits traces to GARL Protocol

This builds a verifiable trust profile for your SK-based agent automatically.
