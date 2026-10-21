"""Access a skill's records database. Dispatch on ``mode``: add / search / modify / delete."""

import asyncio
from collections import Counter
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import sys
import traceback

import yaml

_DEFAULT_EMBED_URL = "http://localhost:3336/v1/embeddings"
_DEFAULT_RERANK_URL = "http://localhost:3337/v1/reranking"


# ------------------------------------------------------------------
#  Config
# ------------------------------------------------------------------


def _load_config() -> dict:
    """Find and load the project ``config/config.yaml``.

    Returns:
        The parsed config mapping, or an empty dict when no file is found.
    """
    for directory in [Path.cwd(), *Path(__file__).resolve().parents]:
        config_path = directory / "config" / "config.yaml"
        if config_path.is_file():
            try:
                with open(config_path, encoding="utf-8") as handle:
                    data = yaml.safe_load(handle)
            except (OSError, yaml.YAMLError):
                return {}
            return data if isinstance(data, dict) else {}
    return {}


_BASIC_OPS = _load_config().get("basic_ops") or {}
EMBED_URL: str = str(_BASIC_OPS.get("embed_url", _DEFAULT_EMBED_URL))
RERANK_URL: str = str(_BASIC_OPS.get("rerank_url", _DEFAULT_RERANK_URL))
RRF_K = 60

STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "not", "if", "then", "so", "than",
        "that", "this", "these", "those", "it", "its", "i", "you", "he", "she",
        "we", "they", "what", "which", "who", "whom", "how", "when", "where",
        "why", "is", "are", "was", "were", "be", "been", "being", "am", "do",
        "does", "did", "have", "has", "had", "to", "of", "in", "for", "on",
        "with", "at", "by", "from", "as", "into", "about", "my", "your", "our",
        "their", "me", "us", "them", "his", "her", "can", "could", "should",
        "would", "will", "shall", "may", "might", "must", "best", "way", "new",
    }
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


# ------------------------------------------------------------------
#  Storage helpers
# ------------------------------------------------------------------


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA_SQL)
    conn.commit()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


# ------------------------------------------------------------------
#  llama.cpp embedding / reranking clients
# ------------------------------------------------------------------


async def _embed(text: str) -> list[float]:
    """Request an embedding for ``text`` from the embedding server.

    Args:
        text: Free text to embed.

    Returns:
        The embedding vector as a list of floats.
    """
    import aiohttp

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                EMBED_URL,
                json={"input": text},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp,
        ):
            data = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"embedding server error {resp.status}: {data}")
            return list(data["data"][0]["embedding"])
    except aiohttp.ClientError as e:
        raise RuntimeError(f"embedding server unavailable at {EMBED_URL}: {e}") from e


async def _rerank(query: str, documents: list[str]) -> list[dict]:
    """Score ``documents`` for relevance to ``query`` using the reranker.

    Args:
        query: Search query text.
        documents: Candidate document texts to score.

    Returns:
        List of ``{"index": int, "relevance_score": float}`` dicts.
    """
    import aiohttp

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                RERANK_URL,
                json={"query": query, "documents": documents},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp,
        ):
            data = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"reranker error {resp.status}: {data}")
            return list(data.get("results", []))
    except aiohttp.ClientError as e:
        raise RuntimeError(f"reranker unavailable at {RERANK_URL}: {e}") from e


# ------------------------------------------------------------------
#  Retrieval scoring
# ------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens from free text, stopwords removed.

    Args:
        text: Free text to tokenize.

    Returns:
        List of lowercase word tokens.
    """
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


def _keyword_scored(
    conn: sqlite3.Connection, keywords: list[str], limit: int, require_all: bool = True
) -> list[tuple[int, float]]:
    """Rank records by exact whole-word term frequency over ``keywords``.

    Each keyword must appear as an exact whole word in a record's content,
    tags or source — it does not match inside a longer word (e.g. ``NTR``
    does not match ``INTRA-ORAL``). With ``require_all`` (the ``keyword``
    submode) a record is kept only if it contains *every* keyword; the score
    is the total number of exact occurrences summed over all keywords.
    Without it (the ``hybrid`` lexical leg) any keyword may match.

    Args:
        conn: An open SQLite connection.
        keywords: List of keywords to match, e.g. ``["NTR", "SE"]``.
        limit: Maximum number of results.
        require_all: Require every keyword to be present.

    Returns:
        List of ``(record_id, score)`` sorted by descending score.
    """
    term_set = frozenset(k.lower().strip() for k in keywords if k and k.strip())
    if not term_set:
        return []
    rows = conn.execute("SELECT id, content, tags, source FROM notes").fetchall()
    scored: list[tuple[int, float]] = []
    for r in rows:
        words = re.findall(r"\w+", f"{r['content']} {r['tags']} {r['source']}".lower())
        counts = Counter(w for w in words if w in term_set)
        if require_all and len(counts) < len(term_set):
            continue
        if not counts:
            continue
        scored.append((r["id"], float(sum(counts.values()))))
    scored.sort(key=lambda kv: -kv[1])
    return scored[:limit]


def _semantic_scored(
    rows: list[sqlite3.Row], query_vec: list[float], limit: int
) -> list[tuple[int, float]]:
    """Rank records by cosine similarity to ``query_vec``.

    Args:
        rows: All record rows.
        query_vec: The query embedding.
        limit: Maximum number of results.

    Returns:
        List of ``(record_id, score)`` sorted by descending score.
    """
    scored: list[tuple[int, float]] = []
    for r in rows:
        sim = _cosine(query_vec, _unpack(r["embedding"]))
        if sim > 0:
            scored.append((r["id"], sim))
    scored.sort(key=lambda kv: -kv[1])
    return scored[:limit]


def _rrf(scored_lists: list[list[tuple[int, float]]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Fuse ranked lists with reciprocal rank fusion.

    Args:
        scored_lists: Ranked lists of ``(record_id, score)``.
        k: RRF smoothing constant.

    Returns:
        List of ``(record_id, rrf_score)`` sorted by descending score.
    """
    scores: dict[int, float] = {}
    for scored in scored_lists:
        for rank, (note_id, _) in enumerate(scored):
            scores[note_id] = scores.get(note_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: -kv[1])


# ------------------------------------------------------------------
#  Operations
# ------------------------------------------------------------------


async def _add(db_path: str, content: str | None, tags: str | None, source: str) -> dict:
    if not content:
        return {"error": "content is required for add"}
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        vec = await _embed(content)
        now = _now()
        cur = conn.execute(
            "INSERT INTO notes (content, embedding, tags, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (content, _pack(vec), tags or "", source, now, now),
        )
        conn.commit()
        return {"id": cur.lastrowid, "status": "added"}
    finally:
        conn.close()


async def _search(
    db_path: str, query: str, top_k: int, submode: str, min_score: float,
    keywords: list[str] | None = None,
) -> dict:
    if submode == "keyword":
        if isinstance(keywords, str) or not keywords:
            return {
                "error": 'keyword search requires "keywords": an explicit list, '
                'e.g. ["NTR", "SE"]'
            }
    elif not query:
        return {"error": "query is required for search"}
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        rows = conn.execute("SELECT * FROM notes").fetchall()
        if not rows:
            return {"query": query, "submode": submode, "matched": False, "results": []}
        by_id = {r["id"]: r for r in rows}

        filtered = 0
        if submode == "keyword":
            pairs = _keyword_scored(conn, keywords, top_k)
        elif submode == "semantic":
            pairs = _semantic_scored(rows, await _embed(query), top_k)
        else:
            pairs, filtered = await _hybrid_search(by_id, conn, rows, query, top_k, min_score)

        results = []
        for note_id, score in pairs[:top_k]:
            r = by_id[note_id]
            results.append(
                {
                    "id": r["id"],
                    "score": round(score, 4),
                    "content": r["content"],
                    "tags": r["tags"],
                    "source": r["source"],
                    "created_at": r["created_at"],
                }
            )
        response = {
            "query": query,
            "submode": submode,
            "matched": bool(results),
            "results": results,
        }
        if submode == "keyword":
            response["keywords"] = keywords
        if filtered > 0:
            response["filtered_out"] = filtered
            response["filter_note"] = (
                f"{filtered} candidate result(s) filtered out due to low relevance "
                f"(reranker score below {min_score})."
            )
        return response
    finally:
        conn.close()


async def _hybrid_search(
    by_id: dict, conn: sqlite3.Connection, rows: list[sqlite3.Row], query: str,
    top_k: int, min_score: float = 0.1,
) -> tuple[list[tuple[int, float]], int]:
    query_vec = await _embed(query)
    keyword = _keyword_scored(conn, _tokenize(query), top_k * 5, require_all=False)
    semantic = _semantic_scored(rows, query_vec, top_k * 5)
    fused = _rrf([keyword, semantic])
    pool = fused[: max(top_k * 2, top_k)]
    if not pool:
        return [], 0
    docs = [by_id[nid]["content"] for nid, _ in pool]
    filtered = 0
    try:
        raw = await _rerank(query, docs)
        scored: list[tuple[int, float]] = []
        for item in raw:
            idx = item.get("index")
            if isinstance(idx, int) and 0 <= idx < len(pool):
                scored.append((pool[idx][0], float(item.get("relevance_score", 0.0))))
        scored.sort(key=lambda kv: -kv[1])
        # min_score is a reranker-relevance threshold; only apply it here.
        kept = [(nid, s) for nid, s in scored if s >= min_score]
        filtered = len(scored) - len(kept)
        if kept:
            return kept[:top_k], filtered
    except Exception:
        pass
    # Rerank failed, or all results fell below min_score.
    # Fall back to embedding (cosine) results.
    return semantic[:top_k], filtered


async def _modify(
    db_path: str, note_id: int, content: str | None, tags: str | None
) -> dict:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return {"error": f"record {note_id} not found"}
        if content is not None:
            vec = await _embed(content)
            conn.execute(
                "UPDATE notes SET content = ?, embedding = ?, tags = ?, updated_at = ? "
                "WHERE id = ?",
                (content, _pack(vec), tags if tags is not None else row["tags"], _now(), note_id),
            )
        elif tags is not None:
            conn.execute(
                "UPDATE notes SET tags = ?, updated_at = ? WHERE id = ?",
                (tags, _now(), note_id),
            )
        else:
            return {"id": note_id, "status": "unchanged"}
        conn.commit()
        return {"id": note_id, "status": "updated"}
    finally:
        conn.close()


async def _delete(db_path: str, note_id: int) -> dict:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        if cur.rowcount == 0:
            return {"error": f"record {note_id} not found"}
        conn.commit()
        return {"id": note_id, "status": "deleted"}
    finally:
        conn.close()


# ------------------------------------------------------------------
#  Dispatch
# ------------------------------------------------------------------


async def run(
    mode: str,
    db_path: str,
    content: str | None = None,
    tags: str | None = None,
    source: str = "",
    note_id: int = 0,
    query: str = "",
    keywords: list[str] | None = None,
    top_k: int = 5,
    min_score: float = 0.1,
    submode: str = "hybrid",
) -> str:
    """Access a skill's records database, dispatching on ``mode``. add inserts a
    record (embedding computed via the embedding server); search ranks records
    by query; modify updates a record's content or tags; delete removes a
    record. search supports submode "hybrid" (default: keyword and semantic
    fused by reciprocal rank fusion, then reranked), "keyword" (exact
    whole-word matching over an explicit ``keywords`` list; every keyword must
    be present), or "semantic".

    Args:
        mode: Operation — "add", "search", "modify", or "delete".
        db_path: Absolute path to the records database file.
        content: (add) Record text to store, or (modify) new text. Omit on
            modify to keep the existing content.
        tags: (add/modify) Optional comma-separated tags. Omit on modify to
            keep the existing tags.
        source: (add) Optional provenance label, e.g. a document or file id.
        note_id: (modify/delete) Id of the record to update or remove.
        keywords: (search, "keyword" submode) Explicit list of keywords, e.g.
            ["NTR", "SE"]. A record must contain every keyword, each as an
            exact whole word. Required for the "keyword" submode.
        query: (search) Search query text, used by "semantic" and "hybrid".
        top_k: (search) Maximum number of results to return. Defaults to 5.
        min_score: (search, hybrid) Minimum reranker relevance score to keep a
            result. Results below this are dropped; when the reranker is
            unavailable, fails, or no result clears the threshold, hybrid falls
            back to the embedding (cosine) results only. Defaults to 0.1; set 0
            to disable the threshold. When results are dropped by the threshold,
            the response includes "filtered_out" (count) and "filter_note"
            (human-readable explanation).
        submode: (search) Ranking — "hybrid", "keyword", or "semantic".
            Defaults to "hybrid". "keyword" requires ``keywords`` and matches
            exact whole words only (all must be present).
    """
    try:
        if mode == "add":
            return json.dumps(await _add(db_path, content, tags, source), ensure_ascii=False)
        if mode == "search":
            return json.dumps(
                await _search(db_path, query, top_k, submode, min_score, keywords),
                ensure_ascii=False,
            )
        if mode == "modify":
            return json.dumps(await _modify(db_path, note_id, content, tags), ensure_ascii=False)
        if mode == "delete":
            return json.dumps(await _delete(db_path, note_id), ensure_ascii=False)
        return f"Unknown mode: {mode!r}. Valid modes: add, search, modify, delete."
    except Exception:
        return json.dumps({"error": traceback.format_exc()})


if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    result = asyncio.run(run(**{k: v for k, v in args.items() if v is not None}))
    sys.stdout.reconfigure(encoding="utf-8")
    print(result)
