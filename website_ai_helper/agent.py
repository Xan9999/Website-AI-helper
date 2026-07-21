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
    "You are a helpful assistant for {site}, embedded ON the site itself — the "
    "visitor is already here. Speak as part of the site ('we', 'our products'), "
    "never in third person ('they', 'their website'). NEVER tell the visitor to "
    "visit 'the official website' or 'learn more on the website' — they are on it. "
    "Link only to a SPECIFIC page when it directly answers the question (a product, "
    "a schedule, a contact page); never link the homepage or the site in general, "
    "and never end with a filler line like 'For more information, visit...'. When "
    "the answer is 'no' or off-topic, include no link at all.\n"
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
    "Language: Always answer entirely in the SAME language as the user's "
    "question, regardless of what language the website content or tool "
    "results are in — translate the relevant facts into the user's language. "
    "Never mix languages in one answer, and never narrate your own reasoning "
    "or intentions (e.g. 'let me check...') — output only the final answer.\n\n"
    "ANSWER, don't redirect: when the provided context contains the actual facts "
    "(dates, times, prices, requirements, steps), state those facts directly in "
    "your answer — never reply with only 'you can find it on page X'. A link is a "
    "supplement to a substantive answer, not a substitute for one. This includes "
    "questions phrased as 'where can I find X' or 'where is X': the user wants X "
    "itself, so give them X from the context first, then add the page link. "
    "Example: asked 'where are the course dates?', list the actual dates from the "
    "context, then link the page for the full/updated list. Only point to a page "
    "without giving the facts when the context genuinely does not contain them.\n\n"
    "Be concise."
    "Do NOT append a separate list of sources or a 'Sources:' line at the end — "
    "the chat interface already displays the sources next to your answer. "
    "When you point the user to a page, write the URL as a markdown link, e.g. "
    "[product page](https://example.com/products/item), and copy URLs EXACTLY "
    "character-for-character from the provided context — never retype or "
    "reconstruct them."
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
            f"{current_page.get('text', '')[:config.PAGE_MAX_CHARS]}"
        )
    sections.append(
        f"---\nUser question: {message}\n"
        "(Reminder: answer with the concrete facts — dates, times, prices, steps — "
        "found in the context above, in the user's language. Do NOT merely point "
        "to a page. A link is allowed only if that specific page directly answers "
        "the question — never the homepage, and never a generic 'for more "
        "information/details visit...' closing line. If the answer is 'no' or the "
        "question is off-topic, politely say no in a sentence and briefly mention "
        "what we DO offer instead — but include no link. Never say 'on our "
        "website' / 'on this site' — the visitor is already browsing it.)"
    )
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
                  temperature=config.TEMPERATURE, stream=True,
                  max_tokens=config.MAX_TOKENS,
                  frequency_penalty=config.FREQUENCY_PENALTY,
                  presence_penalty=config.PRESENCE_PENALTY,
                  extra_body=config.LLM_EXTRA_BODY)
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


def _rewrite_query(client, history: list[dict], message: str) -> str:
    """Rewrite a follow-up message into a standalone search query.

    Why: retrieval embeds ONLY the latest message. In a conversation —
    'do you make winders?' -> 'how much does it cost?' — the follow-up embeds
    as a generic price question with no subject, so vector search returns
    junk and the answer is built on weak context. One small, non-streamed LLM
    call resolves pronouns/ellipsis from the recent history ('how much does
    the automatic winder cost?') before embedding. Only runs when history
    exists, so the first question of a conversation pays zero extra latency.
    Any failure falls back to the raw message — retrieval quality degrades to
    the old behavior, never worse."""
    convo = "\n".join(
        f"{'Visitor' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')[:300]}"
        for m in history[-4:]
    )
    try:
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    "Rewrite the visitor's last message as ONE standalone search query "
                    "for the website's knowledge base. Words like 'it', 'that', 'they', "
                    "'one' MUST be replaced with the thing they refer to in the "
                    "conversation (e.g. after discussing winders, 'how much does it "
                    "cost?' becomes 'how much does the winder cost?'). Keep the "
                    "visitor's language. If the message is already self-contained, "
                    "return it unchanged. Output ONLY the query, nothing else.\n\n"
                    f"Conversation:\n{convo}\n\nVisitor's last message: {message}"
                ),
            }],
            temperature=0.0,
            max_tokens=80,
            extra_body=config.LLM_EXTRA_BODY,
        )
        rewritten = (resp.choices[0].message.content or "").strip().strip('"')
        # A degenerate rewrite (empty, or way longer than a search query
        # should be) means the model went off the rails — keep the original.
        if rewritten and len(rewritten) <= max(200, 3 * len(message)):
            return rewritten
    except Exception:
        pass
    return message


def run_chat(message: str, history: list[dict] | None = None,
             current_page: dict | None = None, collection: str | None = None) -> Iterator[dict]:
    history = history or []
    client = chat_client()

    query = message
    if history and config.QUERY_REWRITE:
        query = _rewrite_query(client, history, message)

    chunks = retrieve(query, collection=collection)
    yield {"type": "sources", "sources": _sources(chunks)}

    messages: list[dict] = [{"role": "system",
                             "content": SYSTEM_PROMPT.format(site=config.site_name_for(collection))}]
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
