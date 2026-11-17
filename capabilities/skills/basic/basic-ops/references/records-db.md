# Records database — `init_db` / `access_db`

Both tools dispatch on a `mode` parameter — `access_db` takes `add`, `search`,
`modify`, `delete`; `init_db` takes only `db_path`.

A skill can keep a database of records: text worth retrieving later, such as the
content of previous documents, sections of legal documents, or an archive of
letters. These two tools define that database and the one way to use it, so every
database behaves the same: one schema, one API, no per-skill variation.

## The database

A database file lives at `references/<name>.db` in the consuming skill; the caller
chooses the file name (e.g. `references/uch_letter_record.db`) and passes its
absolute path as `db_path`. `init_db` creates it (an existing file is left
untouched), `access_db` reads and writes it. Create a fresh database with `init_db`
before a skill's first use.

A single flat table of records:

| Column | Type | Purpose |
|---|---|---|
| id | integer | primary key |
| content | text | the stored record text |
| embedding | blob | vector from the embedding server, for semantic search |
| tags | text | optional comma-separated labels |
| source | text | provenance, e.g. a document or file id |
| created_at | text | ISO-8601 timestamp |
| updated_at | text | ISO-8601 timestamp |

## Embeddings and reranking services

Endpoints come from the project's `config/config.yaml` under `basic_ops` —
`embed_url` and `rerank_url`. When the section or key is absent the scripts fall
back to `http://localhost:3336/v1/embeddings` and
`http://localhost:3337/v1/reranking`. Both are provided by a llama.cpp server and
live outside this skill — the tools assume the endpoints are up.

The reranker runs with a small physical batch size (~512 tokens): feeding it a
long record (or several at once) makes it return HTTP 500 "input is too large".
`access_db` does not trim the candidates. If reranking **fails** (the request
errors, or the server returns no usable scores), hybrid falls back to the
embedding (cosine) results and reports nothing filtered. If reranking
**succeeds** but every score is below `min_score`, `min_score` acts as a hard
filter: hybrid returns an empty result set and reports the dropped count in
`filtered_out`.

## Storing a record (`mode=add`)

When text is worth retrieving later, write it with `access_db mode=add`. Keep one
record to one unit of content — a document's full text, a section, a letter —
specific and self-contained, because a future agent may read it without the
document that produced it. Add a few `tags` naming the topic and set `source` to
the document or file id. The tool embeds the content at write time, so the record
is searchable straight away.

**What to store.** Store the text itself, not a summary of what was done: the
content of a document, a section of a legal document, a past letter's wording, a
paragraph worth quoting. Do not store a working log — a record of what the agent
did this session (edits made, commands run) adds no value, because the skill or
code already reflects those changes.

## Retrieving a record (`mode=search`)

Search before answering a question the stored records should already know, with
`access_db mode=search`. `submode` chooses how:

- `hybrid` (default) — keyword and semantic retrieval fused by reciprocal rank
  fusion, then reranked by the reranker. Use when unsure which signal matters.
- `keyword` — exact whole-word matching over an explicit keyword list
  (`keywords: [...]`); a record must contain every keyword, each as an exact whole
  word. Use for precise multi-keyword lookups. Requires `keywords`.
- `semantic` — embedding similarity. Use for related meaning rather than exact words.

`query` carries the search text for `hybrid` and `semantic`. `top_k` limits the
number of results (default 5); `min_score` sets the minimum reranker relevance
score needed to keep a result (default 0.1; 0 disables the threshold). When
results are dropped by the threshold the response includes `"filtered_out"`
(count) and `"filter_note"` (human-readable explanation).

## Maintaining the database

Correct a stored record with `mode=modify`, passing only the fields that change
(omit `content` to keep it, omit `tags` to keep the existing tags), and remove an
obsolete one with `mode=delete` by `note_id`. Prefer `modify` over adding a
near-duplicate when a record has drifted from the truth.
