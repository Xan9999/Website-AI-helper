"""Structured-database access, exposed to the model as safe, read-only tools.

We expose PARAMETERIZED, read-only functions rather than letting the model
write raw SQL (unreliable and unsafe). The model only picks which function to
call; our code runs the vetted query.

To use your real database:
  1. Replace `_conn()` / `init_demo_db()` with your DB connection (use a
     READ-ONLY user).
  2. Rewrite the tool functions with your real parameterized queries.
  3. Keep the TOOLS schemas in sync so the model knows what's available.
"""
from __future__ import annotations

import sqlite3

from website_ai_helper import config


def _conn() -> sqlite3.Connection:
    config.ensure_data_dir()
    con = sqlite3.connect(config.SQLITE_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_demo_db() -> None:
    """Create and seed a tiny demo DB if it doesn't exist (example data)."""
    con = _conn()
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS products (
               sku TEXT PRIMARY KEY, name TEXT, price REAL,
               in_stock INTEGER, description TEXT)"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS orders (
               id INTEGER PRIMARY KEY, customer TEXT, status TEXT,
               total REAL, placed_on TEXT)"""
    )
    if cur.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?)",
            [
                ("SKU-100", "Aurora Desk Lamp", 49.0, 1, "Warm dimmable LED desk lamp with USB-C charging."),
                ("SKU-101", "Nimbus Wireless Mouse", 29.5, 1, "Silent-click ergonomic mouse, 6-month battery."),
                ("SKU-102", "Terra Standing Mat", 79.0, 0, "Anti-fatigue mat for standing desks (out of stock)."),
                ("SKU-103", "Cobalt Mechanical Keyboard", 119.0, 1, "Hot-swappable keyboard with tactile switches."),
            ],
        )
    if cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO orders VALUES (?,?,?,?,?)",
            [
                (1001, "alice@example.com", "shipped", 78.5, "2026-07-02"),
                (1002, "bob@example.com", "processing", 119.0, "2026-07-09"),
                (1003, "carol@example.com", "delivered", 49.0, "2026-06-28"),
            ],
        )
    con.commit()
    con.close()


# --- Tool implementations — READ ONLY, parameterized ---

def search_products(keyword: str, limit: int = 5) -> list[dict]:
    con = _conn()
    rows = con.execute(
        """SELECT sku, name, price, in_stock, description FROM products
           WHERE name LIKE ? OR description LIKE ? LIMIT ?""",
        (f"%{keyword}%", f"%{keyword}%", int(limit)),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_order_status(order_id: int) -> dict:
    con = _conn()
    row = con.execute(
        "SELECT id, status, total, placed_on FROM orders WHERE id = ?",
        (int(order_id),),
    ).fetchone()
    con.close()
    return dict(row) if row else {"error": f"No order found with id {order_id}"}


# --- OpenAI-style tool schemas + dispatcher ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the product catalog by keyword. Returns name, price, stock status and description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Word or phrase to match in product name/description."},
                    "limit": {"type": "integer", "description": "Max results (default 5)."},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Look up the status, total and date of a specific order by its numeric order id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "The numeric order id, e.g. 1002."},
                },
                "required": ["order_id"],
            },
        },
    },
]

_TOOL_FUNCS = {
    "search_products": search_products,
    "get_order_status": get_order_status,
}


def call_tool(name: str, arguments: dict) -> object:
    fn = _TOOL_FUNCS.get(name)
    if fn is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return fn(**arguments)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
