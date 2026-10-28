# Coding memory Add/Search API

`usage.coding_memory_api` stores ordered engineering histories and returns ranked source memories. It is a general API for a coding agent that needs to reuse past debugging and development experience. Its HTTP routes follow the AML Coding track Add/Search contract.

## Run

Create a file containing one private API key, then start the server:

```bash
PYTHONPATH=src python3 -m usage.coding_memory_api \
  --db /absolute/path/coding-memory.db \
  --key-file /absolute/path/coding-memory.key \
  --host 127.0.0.1 --port 8012
```

The database directory is created automatically. The API key file is read at startup; keep it outside the repository. For a hosted AML smoke, place this service behind a publicly reachable HTTPS endpoint and configure the same key in the AML access request.

## API

- `GET /aml/health` is unauthenticated and returns `{"ok": true}`.
- `POST /aml/add` accepts `request_id`, ordered `messages` (`role`, string `content`, optional Unix-millisecond `timestamp`), `user_id`, and `session_id`. Each successful request is committed to SQLite before HTTP 200. A retry with the same body and `request_id` returns the same response. Reusing that ID with different content returns 409.
- `POST /aml/search` accepts string `query`, `user_id`, and positive integer `top_k`; it returns `{"data": [...]}`. Each item has a stable ID, the original messages in source order, and a timestamp. Results are limited to the exact `user_id` and at most `top_k` entries. Optional `options` are accepted and do not alter evidence retrieval.
- Add and Search accept `X-Api-Key`, `Authorization: Bearer`, or `Authorization: Token`.

Both Add and Search reject malformed input with HTTP 400; missing or incorrect credentials return 401. Search returns source evidence, not a generated answer. SQLite FTS5 ranks code identifier and path tokens alongside ordinary words, with no model or network dependency.

## AML scope

AML's current Coding dataset is CAMBench Coding. Official benchmark tasks and verifier materials are private; the public smoke checks the hosted Add → Search → Answer → Evaluate integration. The local probe in `output/AML_CODING_smoke_2026-10-18.md` checks this API's Add/Search behavior without starting a scored evaluation.

Official references: [AML repository](https://github.com/AML-memory/agent-memory-leaderboard), [AML API guide](https://agentmemoryleaderboard.ai/).
