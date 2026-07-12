"""Orchestrator: hybrid retrieval + structured tools + current-page context.

Flow per turn:
  1. Vector-retrieve relevant chunks from the site knowledge base.
  2. Assemble a grounded prompt (precedence rules + current page + retrieved content).
  3. Stream one completion (tools offered): the model either answers directly
     (streams immediately) or emits tool calls; if so, run them and stream one
     follow-up pass. No separate non-streaming round, no double generation.

Yields SSE-friendly events: {"type":"sources"|"token"|"done"|"error", ...}.
"""
from __future__ import annotations

import json
from collections.abc import Iterator

from website_ai_helper import config, structured
from website_ai_helper.llm import chat_client
from website_ai_helper.retrieval import retrieve

SYSTEM_PROMPT = (
    "You are a helpful assistant for {site}.\n"
    "Answer using ONLY the information provided in this conversation: the Website "
    "content, the Current page, and any Tool results. If none of them contain the "
    "answer, say you don't know and suggest where the user might look. Never invent "
    "facts, prices, or availability.\n\n"
    "Source precedence — when sources disagree, trust them in THIS order:\n"
    "1. Tool results (live database): AUTHORITATIVE for hard facts such as price, "
    "stock/availability, and order status. They OVERRIDE any figures in website "
    "content, which may be out of date.\n"
    "2. Current page: what the user is looking at right now. Use it for questions "
    "about 'this page', but defer to tool results for hard facts.\n"
    "3. Website content: use for explanations, policies, and descriptions. Treat any "
    "prices or availability here as possibly stale — prefer a tool result if one exists.\n\n"
    "IMPORTANT: Product details, prices, stock, and order status live ONLY in the "
    "database tools — not in the website content. Whenever the user asks about a "
    "specific product, its price or availability, or an order, you MUST call the "
    "appropriate tool to look it up before answering. Do not answer such questions "
    "from website content or prior knowledge, and do not assume an item is unavailable "
    "without checking a tool first.\n\n"
    "Be concise. When you use website content, cite it by its [n] label."
)


def _context_block(chunks: list[dict]) -> str:
    if not chunks:
        return "(no relevant website content found)"
    parts = []
    for i, c in enumerate(chunks, 1):
        src = c.get("url") or c.get("source") or "document"
        parts.append(f"[{i}] source=website (crawled, may be outdated) · {src}\n{c.get('text', '')}")
    return "\n\n".join(parts)


def _build_user_message(message: str, chunks: list[dict], current_page: dict | None) -> str:
    sections = [
        "=== WEBSITE CONTENT (retrieved knowledge base — use for explanations/"
        "descriptions; may be outdated) ===\n" + _context_block(chunks)
    ]
    if current_page and current_page.get("text"):
        sections.append(
            "=== CURRENT PAGE (what the user is viewing now — not authoritative for "
            "hard facts) ===\n"
            f"URL: {current_page.get('url', '')}\n"
            f"Title: {current_page.get('title', '')}\n"
            f"{current_page.get('text', '')[:3000]}"
        )
    sections.append(f"---\nUser question: {message}")
    return "\n\n".join(sections)


def _sources(chunks: list[dict]) -> list[dict]:
    return [
        {"n": i, "url": c.get("url", ""), "title": c.get("title", ""),
         "score": round(float(c.get("score", 0.0)), 3)}
        for i, c in enumerate(chunks, 1)
    ]


def _stream_pass(client, messages: list[dict], use_tools: bool) -> Iterator[dict]:
    """Stream ONE completion. Yields {"type":"token",...} for content deltas and
    returns the accumulated tool calls ({"id","name","args"}) via `yield from`."""
    kwargs = dict(model=config.LLM_MODEL, messages=messages,
                  temperature=config.TEMPERATURE, stream=True)
    if use_tools:
        kwargs["tools"] = structured.TOOLS
        kwargs["tool_choice"] = "auto"

    acc: dict[int, dict] = {}
    for chunk in client.chat.completions.create(**kwargs):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "content", None):
            yield {"type": "token", "text": delta.content}
        for tcd in (getattr(delta, "tool_calls", None) or []):
            slot = acc.setdefault(tcd.index, {"id": "", "name": "", "args": ""})
            if tcd.id:
                slot["id"] = tcd.id
            if tcd.function and tcd.function.name:
                slot["name"] += tcd.function.name
            if tcd.function and tcd.function.arguments:
                slot["args"] += tcd.function.arguments
    return [acc[i] for i in sorted(acc)]


def run_chat(message: str, history: list[dict] | None = None,
             current_page: dict | None = None) -> Iterator[dict]:
    history = history or []
    client = chat_client()

    chunks = retrieve(message)
    yield {"type": "sources", "sources": _sources(chunks)}

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT.format(site=config.SITE_NAME)}]
    messages += history[-6:]
    messages.append({"role": "user", "content": _build_user_message(message, chunks, current_page)})

    for iteration in range(config.MAX_TOOL_ITERS + 1):
        use_tools = iteration < config.MAX_TOOL_ITERS  # final pass forces prose
        tool_calls = yield from _stream_pass(client, messages, use_tools)
        if not tool_calls:
            break

        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": t["id"], "type": "function",
                 "function": {"name": t["name"], "arguments": t["args"]}}
                for t in tool_calls
            ],
        })
        for t in tool_calls:
            try:
                args = json.loads(t["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            result = structured.call_tool(t["name"], args)
            messages.append({
                "role": "tool",
                "tool_call_id": t["id"],
                "content": json.dumps(result, default=str),
            })

    yield {"type": "done"}
