from typing import TypedDict,Any

class AgentState(TypedDict,total=False):
    request: Any
    customer_id: str | None
    trace_id: str
    started: float
    client: Any
    plan: Any
    chunks: list
    result: dict
    response: dict
    errors: list
