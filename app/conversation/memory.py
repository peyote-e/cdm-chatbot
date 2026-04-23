from __future__ import annotations

from collections import defaultdict, deque

_MAX_MEMORY_TURNS = 3
_conversation_memory: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=_MAX_MEMORY_TURNS)
)


def store_turn(conversation_id: str | None, question: str, answer: str) -> None:
    if not conversation_id:
        return
    _conversation_memory[conversation_id].append(
        {"question": question, "answer": answer}
    )


def get_history(conversation_id: str | None) -> list[dict[str, str]]:
    if not conversation_id:
        return []
    return list(_conversation_memory.get(conversation_id, []))


def clear_memory() -> None:
    _conversation_memory.clear()
