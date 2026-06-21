# backend/agents/graph/web_node.py
from backend.web.client import web_search
from backend.web.parser import parse_web_results


def retrieve_web_node(state):
    query = state["query"]

    raw_results = web_search(query)
    web_chunks = parse_web_results(raw_results)

    state["web_chunks"] = web_chunks
    return state
