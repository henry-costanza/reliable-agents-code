"""agentkit: the reference library for *Reliable Agents*.

The public API is frozen per version. `api-v<major>.<minor>.json` records it, and a
contract test fails when it drifts; changing it needs a decision record in
docs/adr/ (CLAUDE.md rule 5). The Anthropic adapter lives in
`agentkit.anthropic_provider` and is not imported here, so offline code never
loads the SDK.
"""

from agentkit.budget import OPUS_5_5, Budget, Prices
from agentkit.cassette import CassetteMismatch, open_provider
from agentkit.evals import EvalReport, GoldenTask, contains, exact, finished, run_eval
from agentkit.loop import RunResult, run_agent
from agentkit.messages import (
    Message,
    Opaque,
    Request,
    Response,
    StopReason,
    Text,
    ToolResult,
    ToolSpec,
    ToolUse,
    Usage,
)
from agentkit.provider import Provider, ProviderError, ScriptedProvider
from agentkit.tools import Tool

__version__ = "0.3.0"

__all__ = [
    "OPUS_5_5",
    "Budget",
    "CassetteMismatch",
    "EvalReport",
    "GoldenTask",
    "Message",
    "Opaque",
    "Prices",
    "Provider",
    "ProviderError",
    "Request",
    "Response",
    "RunResult",
    "ScriptedProvider",
    "StopReason",
    "Text",
    "Tool",
    "ToolResult",
    "ToolSpec",
    "ToolUse",
    "Usage",
    "contains",
    "exact",
    "finished",
    "open_provider",
    "run_agent",
    "run_eval",
]
