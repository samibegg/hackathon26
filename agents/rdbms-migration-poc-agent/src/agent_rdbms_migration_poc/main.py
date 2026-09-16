"""RDBMS migration PoC generator — Magenta LangGraph app."""

from __future__ import annotations

import logging
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from magenta_sdklanggraph import App

from agent_rdbms_migration_poc.llm import build_llm
from agent_rdbms_migration_poc.state import MigrationState
from agent_rdbms_migration_poc.system_message import SYSTEM_PROMPT
from agent_rdbms_migration_poc.tools import register

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

app = App(app_name="rdbms-migration-poc-agent")
register(app)


@app.entrypoint
def build_agent() -> CompiledStateGraph:
    logger.info("Building rdbms-migration-poc-agent graph")
    # In AER, call the LLM in-process to avoid invoke_llm → tool-server races during dev reload.
    if os.environ.get("RUNNER_MODE", "").lower() == "aer":
        runtime_llm = build_llm(temperature=0)
    else:
        runtime_llm = app.llm(build_llm(temperature=0))
    tools = app.get_tools()
    llm_with_tools = runtime_llm.bind_tools(app.get_tool_schemas())

    def agent_node(state: MigrationState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            prompt_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        else:
            prompt_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages[1:])
        response = llm_with_tools.invoke(prompt_messages)
        response = app.validate_llm_response(response)
        return {"messages": [response]}

    def should_continue(state: MigrationState) -> Literal["tools", "end"]:
        last = state["messages"][-1]
        return "tools" if hasattr(last, "tool_calls") and last.tool_calls else "end"  # type: ignore[union-attr]

    builder = StateGraph(MigrationState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=app.checkpointer())


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
