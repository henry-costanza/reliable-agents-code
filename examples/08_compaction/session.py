"""Chapter 8: a support conversation that outgrows its context budget.

`Session` keeps the history across customer turns. Before each new turn,
if the last request was larger than `limit` input tokens, it hands the
history to a compactor, which returns notes for the system prompt and the
turns to keep word for word. Three compactors are here: drop the old
turns, summarize them, or write a handoff note with fixed sections plus
the actions the desk recorded. A subagent tool keeps a bulky lookup out
of the main history altogether.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from florist_desk import Desk, log_tool

from agentkit import Provider, Tool, run_agent
from agentkit.messages import (Message, Request, Response, StopReason, Text,
                               ToolResult, ToolUse, Usage)

KEEP = 1  # customer turns every compactor keeps word for word
Compactor = Callable[["Session"], tuple[str, list[Message]]]


@dataclass
class Session:
    provider: Provider
    system: str
    tools: list[Tool]
    compactor: Compactor | None = None
    limit: int = 5000  # input tokens that trigger compaction
    notes: str = ""
    history: list[Message] = field(default_factory=list)
    starts: list[int] = field(default_factory=list)  # turn starts
    calls: list[tuple[str, Usage]] = field(default_factory=list)
    compactions: int = 0

    # --8<-- [start:session]
    def send(self, text: str) -> str:
        """One turn; compact first if the last request was big."""
        over = self.context() > self.limit
        if self.compactor and over and len(self.starts) > KEEP:
            self.notes, self.history = self.compactor(self)
            self.starts = turn_starts(self.history)
            self.compactions += 1
        self.starts.append(len(self.history))
        self.history.append(Message.user(text))
        return self.respond()
    # --8<-- [end:session]

    def prompt(self) -> str:
        return f"{self.system}\n\n{self.notes}" if self.notes else self.system

    def context(self) -> int:
        """Input tokens of the agent's latest request."""
        sizes = [u.input_tokens for kind, u in self.calls if kind == "agent"]
        return sizes[-1] if sizes else 0

    def ask(self, request: Request, kind: str = "agent") -> Response:
        response = self.provider.complete(request)
        self.calls.append((kind, response.usage))
        return response

    def respond(self, max_steps: int = 8) -> str:
        specs = tuple(tool.spec for tool in self.tools)
        by_name = {tool.name: tool for tool in self.tools}
        for _ in range(max_steps):
            response = self.ask(Request(tuple(self.history), self.prompt(), specs))
            self.history.append(response.message)
            calls = response.message.tool_uses
            if response.stop_reason is not StopReason.TOOL_USE or not calls:
                return response.message.text
            results = tuple(
                by_name[c.name].run(c) if c.name in by_name
                else ToolResult(c.id, f"unknown tool {c.name!r}", is_error=True)
                for c in calls)
            self.history.append(Message("user", results))
        return ""


def turn_starts(history: list[Message]) -> list[int]:
    """Where each customer turn begins: user messages that are not results."""
    return [i for i, m in enumerate(history)
            if m.role == "user" and any(isinstance(b, Text) for b in m.content)]


def split(session: Session) -> tuple[list[Message], list[Message]]:
    """The turns to compact, and the last KEEP turns to keep as they are."""
    cut = session.starts[-KEEP]
    return session.history[:cut], session.history[cut:]


def transcript(messages: list[Message]) -> str:
    """The history as plain text, tool calls and results included."""
    lines = []
    for message in messages:
        for block in message.content:
            if isinstance(block, Text):
                who = "Customer" if message.role == "user" else "Agent"
                lines.append(f"{who}: {block.text}")
            elif isinstance(block, ToolUse):
                lines.append(f"Agent called {block.name}({block.input})")
            elif isinstance(block, ToolResult):
                lines.append(f"Result: {block.content}")
    return "\n".join(lines)


# --8<-- [start:drop]
def drop_old_turns(session: Session) -> tuple[str, list[Message]]:
    """Forget everything before the last KEEP turns."""
    _, kept = split(session)
    return session.notes, kept
# --8<-- [end:drop]


# --8<-- [start:summary-prompt]
SUMMARY = ("Summarize the conversation so far so that a "
           "support agent can continue it. Reply with the "
           "summary only.")
# --8<-- [end:summary-prompt]

# --8<-- [start:note-prompt]
NOTE = """\
Write a handoff note so another support agent can continue this
conversation without reading it. Use exactly these four headings:

Customer instructions in force: every instruction, restriction or
preference the customer stated that has not been lifted, quoted word
for word.
Requests done: each request and how it was resolved.
Requests open: anything promised or still unanswered.
Facts for later: ids, amounts, dates and names that a later request
may need, each with the tool or turn it came from.

Leave a heading empty rather than guess. Reply with the note only."""
# --8<-- [end:note-prompt]


def condense(session: Session, instructions: str, old: list[Message]) -> str:
    """One model call that turns old turns, and old notes, into text."""
    earlier = f"Notes from before:\n{session.notes}\n\n" if session.notes else ""
    request = Request(
        (Message.user(f"{earlier}Conversation:\n{transcript(old)}\n\n"
                      f"{instructions}"),),
        system="You condense support conversations for a billing agent.",
        max_tokens=2000)
    return session.ask(request, "compact").message.text.strip()


def summarize(session: Session) -> tuple[str, list[Message]]:
    old, kept = split(session)
    summary = condense(session, SUMMARY, old)
    return f"Summary of the conversation so far:\n{summary}", kept


HANDOFF = "Handoff note for the conversation so far:"
RECORDED = ("Actions Brindle's system recorded in this conversation "
            "(authoritative):")


# --8<-- [start:handoff]
def handoff(desk: Desk) -> Compactor:
    """A note in fixed sections, plus the desk's record."""
    def compact(session: Session) -> tuple[str, list[Message]]:
        old, kept = split(session)
        note = condense(session, NOTE, old)
        # A note rebuilt from an older one may copy its action list.
        note = note.split("\n\nActions Brindle's system recorded")[0]
        done = [f"- {a}" for a in desk.actions()] or ["- none"]
        return (f"{HANDOFF}\n{note}\n\n{RECORDED}\n"
                + "\n".join(done)), kept
    return compact
# --8<-- [end:handoff]


# --8<-- [start:subagent-prompt]
SUBAGENT = ("You answer one question from a customer's Brindle "
            "activity log. Call get_activity_log, then answer in at "
            "most two sentences, citing the entry ids you relied on.")
# --8<-- [end:subagent-prompt]


# --8<-- [start:subagent]
def log_reader(session: Session) -> Tool:
    """A tool that hands the question to a subagent."""
    def ask(question: str) -> str:
        result = run_agent(session.provider, question, max_steps=4,
                           system=SUBAGENT, tools=[log_tool()])
        usage = [("subagent", u) for u in result.step_usage]
        session.calls.extend(usage)
        if not result.ok:
            raise RuntimeError("the subagent did not finish")
        return result.final_text
    # --8<-- [end:subagent]
    return Tool("ask_activity_log",
                "Ask a question about the customer's 2026 activity log: who "
                "did what in their Brindle account, and when. A reader with "
                "the whole log answers it and cites entry ids.",
                {"type": "object", "properties": {"question": {
                    "type": "string", "minLength": 1}},
                 "required": ["question"], "additionalProperties": False},
                ask)
