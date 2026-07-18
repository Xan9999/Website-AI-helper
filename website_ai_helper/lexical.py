"""Lexical (sparse-vector) text encoding for hybrid retrieval.

Dense embeddings (bge-m3) capture MEANING but are weak at exact identifiers:
a query for "EXT120" embeds close to generic machinery text, not specifically
to the one chunk containing that model number. Classic keyword search has the
opposite profile. Hybrid retrieval runs both and fuses the rankings — see
vectorstore.search().

This module provides the keyword half as Qdrant sparse vectors:

- Tokenize on unicode word characters, lowercase.
- Map each token to a stable 31-bit id by hashing (no vocabulary file to
  build, ship, or keep in sync; ~2 billion id space makes collisions between
  tokens that BOTH matter for the same query vanishingly unlikely).
  Python's built-in hash() is salted per process, so md5 is used instead —
  ids must be identical between the ingest run and every later query.
- Weights are raw term frequencies. Rarity weighting (IDF) is applied
  server-side by Qdrant (the collection's sparse field is created with
  Modifier.IDF), computed over the live collection — so weights stay correct
  as documents are added, with no client-side corpus statistics.

The result scores like BM25 without its length normalization, which is fine
here because chunks are already cut to a uniform CHUNK_SIZE.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _normalize(token: str) -> str:
    """Lowercase and fold diacritics (čelada -> celada). Visitors routinely
    type Slovenian/Italian/etc. without accents; folding both sides at index
    AND query time makes 'celade' match 'čelade' exactly."""
    decomposed = unicodedata.normalize("NFKD", token.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _token_id(token: str) -> int:
    """Stable 31-bit id for a token (identical across processes and runs)."""
    return int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:4], "big") & 0x7FFFFFFF


def sparse_encode(text: str) -> tuple[list[int], list[float]]:
    """Encode text as parallel (indices, values) lists for a Qdrant sparse
    vector: hashed token ids and their term frequencies. Returns empty lists
    for text with no word tokens (caller should then skip lexical search)."""
    counts = Counter(_token_id(_normalize(t)) for t in _TOKEN_RE.findall(text))
    return list(counts.keys()), [float(v) for v in counts.values()]
