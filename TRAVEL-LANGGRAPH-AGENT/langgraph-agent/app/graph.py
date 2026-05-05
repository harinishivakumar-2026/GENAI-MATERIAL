from contextlib import ExitStack

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.config import (
    CHECKPOINTER_TYPE,
    LANGGRAPH_POSTGRES_POOL_MAX_IDLE,
    LANGGRAPH_POSTGRES_POOL_MAX_SIZE,
    LANGGRAPH_POSTGRES_POOL_MIN_SIZE,
    LANGGRAPH_POSTGRES_SETUP,
    LANGGRAPH_POSTGRES_URI,
    logger,
)
from app.nodes import flight_agent, hotel_agent, input_processor_node
from app.state import TravelState


builder = StateGraph(TravelState)

builder.add_node("processor", input_processor_node)
builder.add_node("flights", flight_agent)
builder.add_node("hotels", hotel_agent)

builder.set_entry_point("processor")
builder.add_edge("processor", "flights")
builder.add_edge("flights", "hotels")
builder.add_edge("hotels", END)


_exit_stack = ExitStack()


def _build_checkpointer():
    if CHECKPOINTER_TYPE == "postgres":
        if not LANGGRAPH_POSTGRES_URI:
            raise RuntimeError("CHECKPOINTER_TYPE=postgres requires LANGGRAPH_POSTGRES_URI or DATABASE_URL")

        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            conninfo=LANGGRAPH_POSTGRES_URI,
            min_size=LANGGRAPH_POSTGRES_POOL_MIN_SIZE,
            max_size=LANGGRAPH_POSTGRES_POOL_MAX_SIZE,
            max_idle=LANGGRAPH_POSTGRES_POOL_MAX_IDLE,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
            open=True,
        )
        _exit_stack.callback(pool.close)

        checkpointer = PostgresSaver(pool)
        if LANGGRAPH_POSTGRES_SETUP:
            logger.info("Running LangGraph Postgres checkpointer setup")
            checkpointer.setup()
        logger.info(
            "Using Postgres checkpointer for LangGraph state with pool min=%s max=%s max_idle=%s",
            LANGGRAPH_POSTGRES_POOL_MIN_SIZE,
            LANGGRAPH_POSTGRES_POOL_MAX_SIZE,
            LANGGRAPH_POSTGRES_POOL_MAX_IDLE,
        )
        return checkpointer

    logger.info("Using in-memory checkpointer for LangGraph state")
    return MemorySaver()


checkpointer = _build_checkpointer()
graph = builder.compile(checkpointer=checkpointer)
