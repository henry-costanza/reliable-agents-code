"""Chapter 9: chapter 8's handoff note, with its stop reason checked.

Chapter 8's `condense` used whatever text came back, even when the model
stopped at `max_tokens`. Here every condensing call must end its turn: a
note cut off is asked for again with twice the room, and a second cut
raises `Truncated` instead of passing half a note on. The prompt also
asks for ids instead of copied tables, which is what filled the notes.
"""

from dataclasses import replace

import chapters  # noqa: F401  (chapter 8's code on the import path)
from florist_desk import Desk
from session import HANDOFF, NOTE, RECORDED, Compactor, Session, split, transcript

from agentkit.messages import Message, Request, StopReason

IDS = ("Do not copy tables or lists of records. Give their ids and the\n"
       "tool that returns them; the agent can fetch them again.\n")
assert "\nLeave a heading empty" in NOTE
# --8<-- [start:note-ids]
NOTE_IDS = NOTE.replace("\nLeave a heading empty",
                        "\n" + IDS + "Leave a heading empty")
# --8<-- [end:note-ids]


class Truncated(Exception):
    """A model call stopped at max_tokens twice."""


# --8<-- [start:finished]
def finished(session: Session, request: Request, kind: str) -> str:
    """The reply's text, only if the model ended its turn."""
    for room in (request.max_tokens, 2 * request.max_tokens):
        request = replace(request, max_tokens=room)
        response = session.ask(request, kind)
        if response.stop_reason is StopReason.END_TURN:
            return response.message.text.strip()
        if response.stop_reason is not StopReason.MAX_TOKENS:
            break
    raise Truncated(f"{kind} call stopped with "
                    f"{response.stop_reason.value} at {room} tokens")
# --8<-- [end:finished]


def condense(session: Session, old: list[Message]) -> str:
    earlier = f"Notes from before:\n{session.notes}\n\n" if session.notes else ""
    request = Request(
        (Message.user(f"{earlier}Conversation:\n{transcript(old)}\n\n"
                      f"{NOTE_IDS}"),),
        system="You condense support conversations for a billing agent.",
        max_tokens=2000)
    return finished(session, request, "compact")


def checked_handoff(desk: Desk) -> Compactor:
    """Chapter 8's handoff note, built with `finished`."""
    def compact(session: Session) -> tuple[str, list[Message]]:
        old, kept = split(session)
        note = condense(session, old)
        note = note.split("\n\nActions Brindle's system recorded")[0]
        done = [f"- {a}" for a in desk.actions()] or ["- none"]
        return (f"{HANDOFF}\n{note}\n\n{RECORDED}\n"
                + "\n".join(done)), kept
    return compact
