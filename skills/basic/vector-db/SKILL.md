---
name: vector-db
description: >
  Store and retrieve records and text as a searchable database. Defines the
  schema and API used by a skill's records database, and provides tools to
  initialise, add, search, modify, and delete records. Search fuses keyword and
  semantic (embedding) retrieval by reciprocal rank fusion and reranks with a
  reranker. Use whenever the agent needs to store document text, index a corpus
  or archive, record sections of documents, or search stored records by meaning
  or keyword, even if the user does not name this skill.
---

# Vector Database

A skill can keep a database of records: text worth retrieving later, such as the
content of previous documents, sections of legal documents, or an archive of
letters. This skill defines that database and the one way to use it, so every
database behaves the same.

## Purpose

Give the agent one uniform place to store and search records, so a body of text
accumulates across sessions instead of being re-read or lost. One schema, one
API, no per-skill variation. The agent indexes records into the database and
searches them by meaning or keyword, without needing to know how storage or
retrieval work underneath.

## Deliverable

A database file at `references/<name>.db` in the consuming skill, plus two
tools: `init_db` to create it, and `access_db` to read and write it. The caller
chooses the file name (e.g. `references/uch_letter_record.db`); pass its absolute
path as `db_path`.

The database is a single flat table of records:

| Column | Type | Purpose |
|---|---|---|
| id | integer | primary key |
| content | text | the stored record text |
| embedding | blob | vector from the embedding server, for semantic search |
| tags | text | optional comma-separated labels |
| source | text | provenance, e.g. a document or file id |
| created_at | text | ISO-8601 timestamp |
| updated_at | text | ISO-8601 timestamp |

Embeddings come from an external server at `http://localhost:3336/v1/embeddings`,
and reranking from `http://localhost:3337/v1/reranking`. Both are provided by a
llama.cpp server and live outside this skill — the tools assume the endpoints are
up. The reranker runs with a small physical batch size (~512 tokens): feeding it
a long record (or several at once) makes it return HTTP 500 "input is too large".
`access_db` does not trim the candidates; if reranking fails or every score falls
below `min_score`, hybrid falls back to the embedding (cosine) results only, so a
failure never empties the result set.

## Methodology

### Storing a record

When text is worth retrieving later, write it with `access_db` `mode=add`. Keep
one record to one unit of content — a document's full text, a section, a letter —
specific and self-contained, because a future agent may read it without the
document that produced it. Add a few tags naming the topic and set `source` to
the document or file id. The tool embeds the content at write time so the record
is searchable straight away.

**What to store.** Store the text itself, not a summary of what was done: the
content of a document, a section of a legal document, a past letter's wording, a
paragraph worth quoting. Do not store a working log — a record of what the agent
did this session (edits made, commands run) adds no value, because the skill or
code already reflects those changes.

### Retrieving a record

Search before answering a question the stored records should already know, with
`access_db` `mode=search`. The `submode` chooses how:

- `hybrid` (default) — keyword and semantic retrieval fused by reciprocal rank
  fusion, then reranked by the reranker. Use when unsure which signal matters.
- `keyword` — literal term matching. Use for a specific phrase.
- `semantic` — embedding similarity. Use for related meaning rather than exact
  words.

### Maintaining the database

Correct a stored record with `mode=modify`, passing only the fields that change,
and remove an obsolete one with `mode=delete`. Prefer `modify` over adding a
near-duplicate when a record has drifted from the truth. Create a fresh database
with `init_db` before a skill's first use.

## Keywords

records, text, document, corpus, archive, embedding, semantic, keyword, hybrid,
reciprocal rank fusion, rerank, tags, source, search.
