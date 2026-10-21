# Batch patterns

Use these patterns when `spawn_many` is not flexible enough — for example when
each task needs a different skill or tool set derived from a list.

## Reuse the client

`_client.py` lives beside this reference's skill scripts. Add that directory to
`sys.path`, then call its async helpers. The system prompt lists the skill's
absolute directory, so use that path.

The tool runner caps a tool subprocess at about 10 minutes. Keep blocking
`wait` calls under that bound (540 seconds is a safe default); for longer work,
submit with `wait=False`, return the job ids, and poll with `status` later.

```python
import asyncio
import json
import sys

sys.path.insert(0, r"<absolute path to the subagent skill>/scripts")
import _client


async def main() -> None:
    prompts = [f"Summarise part {i} of C:/work/input.txt" for i in range(1, 6)]
    records = await _client.spawn_many(
        [
            {
                "prompt": prompt,
                "activated_skills": ["basic/basic-ops"],
                "tools": ["read_file"],
            }
            for prompt in prompts
        ],
        wait=False,
    )
    results = await asyncio.gather(*(_client.wait(r["id"], timeout=540) for r in records))
    print(json.dumps(results, ensure_ascii=False))


asyncio.run(main())
```

## Staggered submission

For large batches, submit in chunks so the queue and memory stay predictable.

```python
async def run_chunks(items: list[str], size: int = 10) -> list[dict]:
    results: list[dict] = []
    for start in range(0, len(items), size):
        chunk = items[start : start + size]
        records = await _client.spawn_many(
            [{"prompt": item, "tools": ["read_file"]} for item in chunk]
        )
        results.extend(await asyncio.gather(*(_client.wait(r["id"], timeout=540) for r in records)))
    return results
```

## Discover the endpoint

The client resolves the endpoint in this order:

1. `PROCOO_SUBAGENT_URL` environment variable.
2. `subagent.host` / `subagent.port` in `config/config.yaml`.
3. `http://127.0.0.1:12842`.

The API key resolves from `PROCOO_SUBAGENT_API_KEY`, then
`subagent.api_keys`, then `auth.api_keys`.

## Handle failures

`wait` returns the record even when the run failed. Check `status` and `error`
per record; do not assume a batch is all-or-nothing.

```python
for record in results:
    if record["status"] != "done":
        print(record["id"], record["status"], record["error"])
```
