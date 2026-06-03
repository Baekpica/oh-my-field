from collections.abc import Callable
from typing import Final

from langgraph.graph.state import CompiledStateGraph

START: Final[str]
END: Final[str]

class StateGraph[StateT, ContextT, InputT, OutputT]:
    def __init__(self, state_schema: type[StateT]) -> None: ...
    def add_node(
        self,
        node: str,
        action: Callable[[StateT], StateT],
    ) -> StateGraph[StateT, ContextT, InputT, OutputT]: ...
    def add_edge(
        self,
        start_key: str,
        end_key: str,
    ) -> StateGraph[StateT, ContextT, InputT, OutputT]: ...
    def compile(self) -> CompiledStateGraph[StateT, ContextT, InputT, OutputT]: ...
