# Deployment runbook and pre-deployment audit

Two parts: the **audit record** — every problem found before going live, why it
mattered, the fix, and how it was verified — and the **runbook** for actually
deploying.

---

# Part 1 — Audit record

The app was feature-complete and the UI signed off. This audit asked only one
question: *can this go live?* The answer was no, for five reasons. Two of them
were correctness and privacy bugs in the headline "upload your own document"
feature rather than deployment mechanics.

The eval harness could not have caught either, because it only ever exercises
the seeded demo corpus — which is loaded directly into Postgres, bypassing the
upload path entirely.

## Blockers

### B1 — Uploads failed for any document over ~128 chunks

**What was wrong.** `embed_chunks` sent every chunk of a document to Voyage in a
single `client.embed()` call. The Voyage API accepts at most 128 texts per
request; the SDK names that limit (`voyageai.VOYAGE_EMBED_BATCH_SIZE = 128`) but
`client.embed` does not split for you — it forwards the list whole.

**Why it mattered.** At ~110 words per chunk, 128 chunks is roughly 25–30 pages.
Any longer document produced an API error, and because the upload route had no
error handling around ingest, it surfaced as a bare HTTP 500. In other words the
feature the landing page invites you to use was broken for most real documents.

**Why it was never noticed.** Every document ever ingested through the UI during
development was one chunk (a synthetic test PDF) or thirteen (the handbook,
seeded directly). The failure threshold sat an order of magnitude above anything
that had been tried.

**The fix.** `embed_chunks` now iterates in slices of `EMBED_BATCH_SIZE` and
concatenates the results in order, so the returned list still lines up
index-for-index with its input. The upload route also rejects documents above
`MAX_CHUNKS_PER_DOCUMENT` *before* embedding, so an oversized file costs nothing.

**Verified.** `tests/test_embedding_batching.py` runs a fake client that raises
if handed more than 128 texts — the same way the real API does — and asserts one
embedding per chunk and `ceil(n/128)` calls for n up to 1200. One test pins the
original failure shape so a regression is unambiguous.

### B2 — Every blocked-storage visitor shared one session

**What was wrong.** `sessionId()` in `frontend/src/api.ts` returned the literal
string `'ephemeral'` whenever `localStorage` threw.

**Why it mattered.** Retrieval is scoped by session id. Private browsing,
blocked cookies and several in-app browsers all hit that branch, so every one of
those visitors sent `x-session-id: ephemeral` — and would read each other's
uploaded documents. This reintroduced precisely the cross-tenant leak that
session scoping was built to close, for the subset of users least likely to
expect it.

**The fix.** The fallback is now a `crypto.randomUUID()` generated once per tab
and held in a module-level constant. Blocked-storage visitors are isolated from
each other; the only thing they lose is persistence across reloads.

**Verified.** `tests/test_session_and_config.py` asserts the literal
`'ephemeral'` is rejected server-side as a malformed session id, so even a stale
cached bundle cannot reach a shared scope.

### B3 — No rate limit or cost cap on paid endpoints

**What was wrong.** `/ask` and `/documents` were unauthenticated and unbounded.

**Why it mattered.** `/ask` costs roughly a cent per call — an embedding, a
rerank, and two or three Claude calls. A single loop against it runs up real
spend with no ceiling. `/documents` is worse in a different way: a 5 MB PDF is
about 4,300 chunks and 17 MB of vectors, so repeated uploads fill the database
rather than the invoice.

**The fix.** Four layers:

| Layer | Limit | Where |
|---|---|---|
| Per-IP rate limit | 10/min, 100/day on `/ask`; 3/min, 20/day on `/documents` | `app/limiter.py` |
| Upload size | 5 MB, down from 20 MB | `config.MAX_UPLOAD_BYTES` |
| Per-document | 1,200 chunks, checked before embedding | `config.MAX_CHUNKS_PER_DOCUMENT` |
| Per-session | 5 documents / 3,000 chunks | `config.MAX_*_PER_SESSION` |

The 20 MB cap was actively dangerous: such a PDF is ~17,000 chunks and ~68 MB of
vectors, enough to exhaust a free-tier database in a handful of uploads.

**Verified.** Live: the fourth upload inside a minute returns
`429 Rate limit exceeded: 3 per 1 minute`.

### B4 — The health check passed while the app was broken

**What was wrong.** `app.main` imported cleanly with `DATABASE_URL`,
`ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` all unset, and `/health` returned
`{"status": "ok"}` unconditionally.

**Why it mattered.** Render's health check would go green and route traffic to
an instance where every single request failed. A deploy missing one environment
variable would look successful.

**The fix.** Two changes. `config.require_env()` runs in the FastAPI lifespan and
raises `ConfigError` naming the missing variables, so a misconfigured deploy
crashes on boot instead of serving errors. And `/ready` was added, which executes
`SELECT 1`; the platform health check points there. `/health` remains as a pure
liveness ping that deliberately does no I/O.

**Verified.** `tests/test_session_and_config.py` parametrises over each required
variable and asserts startup fails naming it. Live: `/ready` returns
`{"status":"ready","database":"ok"}`.

### B5 — Nothing to deploy with

No Dockerfile, no blueprint, no `.env.example`, no README, no Python pin. Worse,
`main.py` fell back to a localhost-only CORS regex when `ALLOWED_ORIGINS` was
unset — so a production deploy that forgot it would fail in the browser with an
opaque CORS error rather than anything diagnosable.

**The fix.** `Dockerfile` (pinned 3.14, non-root, layer-cached deps),
`render.yaml` (API + static site + cleanup cron, secrets as `sync: false`),
`.env.example`, `README.md`, and this document. `require_env()` now refuses to
start when `ENVIRONMENT=production` and `ALLOWED_ORIGINS` is unset.

### B6 — A truncated verifier response still returned a 500

**Found during verification of the other fixes, not in the audit itself.** While
load-testing `/ask`, one request in fourteen returned a 500:

```
pydantic_core.ValidationError: 1 validation error for Verification
  Invalid JSON: EOF while parsing a string at line 1 column 1370
  input_value='{"grounded": true, "issu...]}]}]}]}]}]}]}]}]}]}'
```

**What was wrong.** The original audit's first finding was that a malformed
verifier response took down the request it was meant to protect. Moving to
structured outputs was supposed to close that permanently. But structured
outputs guarantee the *shape* of a **completed** response — not that generation
completes. Given a degenerate question the verifier ran to `max_tokens`,
emitting repeated `]}` until it was cut off mid-JSON, and `messages.parse`
raised a `ValidationError` that nothing caught.

**Why it mattered.** Same failure as before, by a new route: the safety net
crashing the request whose answer had already been generated successfully.

**The fix.** `call_claude_structured` now catches `ValidationError` and also
rejects a `stop_reason` of `max_tokens`, converting both to `LLMError`. Since
`verify_answer` already fails open on `LLMError`, the answer survives and the
trace records that verification could not run.

**Verified.** `tests/test_generation_errors.py` covers all three failure modes
(truncated JSON, max_tokens, no output) and asserts that `verify_answer` fails
open in each — the property that actually matters.

**Worth noting for the future:** this is the second time this exact failure has
appeared in a different disguise. The lesson is that the verification step must
never be able to fail the request, and that is now pinned by a test rather than
by the current implementation happening to be correct.

## High severity

### H1 — Database errors were unhandled
Only `LLMError` was translated. A `psycopg2.OperationalError` became an opaque
500. Both routes now catch `psycopg2.Error` and return **503** with a clear
message, logged with a stack trace server-side.

### H2 — Six connection sites, no pooling
A single `/ask` opened three separate connections — vector search, keyword
search, embedding fetch — each a fresh TCP and TLS handshake on the request's
critical path. Negligible against a local database, material against Neon, and
it scales concurrency straight into the provider's connection cap.

Replaced with a module-level `ThreadedConnectionPool` behind a `get_connection()`
context manager, so every call site kept its shape. Threaded rather than simple
because the routes are sync `def` and therefore run in FastAPI's threadpool. A
connection that raised is closed rather than returned, so a broken socket is
never handed to the next caller. The pool is closed on shutdown.

### H3 — Session uploads never expired
Nothing deleted an uploaded document, so the table grew without bound.
`seed/cleanup_sessions.py` removes session-scoped chunks older than
`SESSION_TTL_DAYS` (7); `render.yaml` runs it nightly at 03:00. The demo corpus
(`session_id IS NULL`) is never touched.

### H4 — `x-session-id` was trusted unvalidated
A client-supplied header written straight into the database with no check on
shape or length. `valid_session_id()` now requires a UUID. Anything else is
treated as *no session*, which limits the caller to the shared demo corpus
rather than failing their request; uploads, which need a real session, return
400. Tested against SQL-ish input, path traversal, and a 10,000-character value.

## Cleanup

- Removed the `/corpus` endpoint, `api.corpus()` and `CorpusStatus` — nothing had
  called them since the hero was restructured.
- Removed `sample_chunks` and `word_count` from the upload response; the UI
  stopped rendering them when the ingest confirmation was simplified.
- `chunk_text` now raises on `overlap >= chunk_size` instead of producing a
  zero step. Unreachable with current constants, but it was a `ValueError`
  waiting for a future edit.
- Structured logging (`logging.basicConfig`) replacing reliance on stack traces,
  with ingest and rejection events logged.
- Added `tests/` — 45 tests covering chunking boundaries, the embedding batcher,
  RRF arithmetic, the visibility clause, retrieval scoring, session-id
  validation and environment validation. No API spend.

## Checked and found healthy — no action

- `.env` has never been committed (full history checked); no secrets in tracked files.
- `npm audit --omit=dev`: 0 vulnerabilities.
- Session scoping is correctly enforced server-side, including when a
  `document_id` is supplied — passing someone else's id matches nothing rather
  than leaking it, because the session predicate is always ANDed in.
- Schema, HNSW and GIN indexes, and an idempotent seed script all present.
- Eval holds at 13/13 recall, 13/13 correct, mean MRR 0.962.

## Known limitations

- **The Docker image has not been built.** Docker is not installed on the
  development machine, so `Dockerfile` and `render.yaml` are written but
  unverified. Expect to iterate on the first deploy.
- **Rate limits are per-instance and in-memory.** Correct for a single Render
  instance. Scaling out needs a shared Redis backend (`storage_uri` on the
  `Limiter`).
- **Session ids are unauthenticated bearer tokens.** A UUID is unguessable, but
  it is not signed — anyone who obtains one can read that session's documents.
  Acceptable for a demo where uploads are transient and user-supplied.
- **Prompt injection is possible within a session.** Retrieved chunks are
  interpolated into the prompt, so a malicious PDF can carry instructions. Blast
  radius is the uploader's own session.
- **`<->` is L2, not cosine.** Voyage returns normalised vectors so the ranking
  is identical today. Switching to `<=>` would need the HNSW index rebuilt with
  `vector_cosine_ops` — worth doing at Neon setup or not at all.

---

# Part 2 — Deployment runbook

Backend on Render (Docker), Postgres on Neon, frontend as a Render static site,
plus a nightly cleanup job on GitHub Actions. Roughly 30–45 minutes end to end.

**Why the cleanup isn't a Render cron:** Render has no free plan for cron
services, so the blueprint would be rejected. GitHub Actions runs it for free and
is the better home anyway — it doesn't depend on the Render web service being
awake, which a free instance isn't when it's been idle.

## Before you start

You need: a GitHub repo with this code pushed, a Neon account, a Render account,
and your two API keys.

**The one ordering trap.** `VITE_API_BASE` is compiled into the frontend bundle
at build time, and the API's `ALLOWED_ORIGINS` has to name the frontend. Each
needs the other's URL. Render URLs are predictable — `https://<service-name>.onrender.com`
— so with the names in `render.yaml` you can set both up front:

| Variable | Value |
|---|---|
| `VITE_API_BASE` | `https://rag-inspector-api.onrender.com` |
| `ALLOWED_ORIGINS` | `https://rag-inspector-web.onrender.com` |

If either name is already taken globally, Render appends a suffix. Check the
real URLs after step 3 and correct both if they differ.

---

## Step 1 — Database (Neon)

1. Create a Neon project. Any region; pick one near your Render region.
2. From the dashboard copy **both** connection strings:
   - **Direct** (host has no `-pooler`) — used once, for schema and seeding.
   - **Pooled** (host contains `-pooler`) — used by the app.
3. Enable pgvector. Neon's SQL Editor, or the psql in step 2, will do it —
   `schema.sql` starts with `CREATE EXTENSION IF NOT EXISTS vector;`.

## Step 2 — Schema and demo corpus

Run from your machine, pointed at Neon. Use the **direct** string here: DDL and
`CREATE EXTENSION` are more reliable outside the connection pooler.

```bash
# Windows PowerShell
$env:DATABASE_URL = "postgresql://...neon.tech/neondb?sslmode=require"   # DIRECT

psql $env:DATABASE_URL -f schema.sql        # or paste schema.sql into Neon's SQL Editor
python -m seed.seed_demo_corpus
```

The seed script re-embeds the 13 handbook chunks, so `VOYAGE_API_KEY` must be in
your local `.env`. Expect `Seeded 13 chunks as document 'demo-meridian-handbook'`.

Confirm:

```sql
SELECT count(*) FROM chunks WHERE session_id IS NULL;   -- 13
SELECT indexname FROM pg_indexes WHERE tablename = 'chunks';
-- expect chunks_pkey, chunks_embedding_hnsw, chunks_text_fts,
--        chunks_session_id, chunks_document_id, chunks_document_chunk
```

If the HNSW index is missing, vector search silently falls back to a sequential
scan — correct results, much slower as the table grows.

## Step 3 — Create the Render services

Push to GitHub, then in Render: **New → Blueprint**, select the repo. It reads
`render.yaml` and creates two services:

| Service | Type | What it is |
|---|---|---|
| `rag-inspector-api` | Docker web service | The FastAPI backend |
| `rag-inspector-web` | Static site | The built frontend |

The nightly cleanup is a GitHub Actions workflow, configured separately in
step 4b.

The first build will fail or the API will crash-loop until step 4 — that is
expected, because `require_env()` refuses to start without its variables.

## Step 4 — Environment variables

In the Render dashboard, set these (every one is `sync: false`, so none of them
are in the repo):

**`rag-inspector-api`**

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** string |
| `ANTHROPIC_API_KEY` | your key |
| `VOYAGE_API_KEY` | your key |
| `ALLOWED_ORIGINS` | `https://rag-inspector-web.onrender.com` |
| `ENVIRONMENT` | `production` (already set by the blueprint) |

**`rag-inspector-web`**

| Variable | Value |
|---|---|
| `VITE_API_BASE` | `https://rag-inspector-api.onrender.com` |

### 4b — The cleanup job (GitHub Actions)

`.github/workflows/cleanup.yml` runs nightly at 03:00 UTC. It needs one
repository secret:

**Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** connection string |

It talks to Postgres and nothing else, so it is deliberately not given the model
API keys.

Verify it without waiting for the schedule: **Actions → Clean up expired
sessions → Run workflow**. It should log
`Removed 0 session chunk(s) older than 7 day(s).` — zero is correct on a fresh
database and still proves the secret and connection work.

Then redeploy both. If you changed `VITE_API_BASE` you must rebuild the static
site — it is baked into the bundle, not read at runtime.

## Step 5 — Verify the deploy

```bash
curl https://rag-inspector-api.onrender.com/health   # {"status":"ok"}
curl https://rag-inspector-api.onrender.com/ready    # {"status":"ready","database":"ok"}
```

`/health` only proves the process started. `/ready` proves it can reach Postgres
— that is the one that matters, and it is what Render's health check uses.

Then in the browser:

1. Load the site. Click **Use the sample document**, ask a sample question.
2. Click **See how it works** and confirm all eight scenes render with real
   numbers — especially scene 04, which should show chunks found by both
   searches outranking chunks found by one.
3. Upload a PDF of **at least 40 pages**. This is the B1 regression check: under
   the old code anything past ~128 chunks returned a 500.
4. Ask a question about the uploaded document and confirm the answer comes from
   your document, not the handbook.

Finally confirm the limiter bites — sequential requests won't trip the
per-minute limit because each `/ask` takes several seconds, so send them at once:

```bash
seq 1 16 | xargs -P 16 -I{} curl -s -o /dev/null -w "%{http_code} " \
  -X POST https://rag-inspector-api.onrender.com/ask \
  -H 'Content-Type: application/json' -d '{"question":"test"}'
# expect a mix of 200 and 429
```

## Step 6 — Set spend caps

Do this before sharing the URL. The rate limiter is a control, not a guarantee.

- **Anthropic Console → Billing → spend limits.**
- **Voyage dashboard → usage limits.**

At roughly a cent per question and the default limits, a single IP can spend
about $1/day. A dozen IPs is a dozen dollars. Caps at the provider are the only
hard stop.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| API crash-loops on boot, logs name a variable | `require_env()` doing its job | Set the named variable, redeploy |
| Browser console shows CORS errors | `ALLOWED_ORIGINS` doesn't exactly match the site's origin | Match scheme and host exactly, no trailing slash |
| Frontend calls `localhost:8000` | `VITE_API_BASE` wasn't set at **build** time | Set it, then rebuild the static site |
| `/ready` returns 503 | Wrong `DATABASE_URL`, or `sslmode=require` missing | Use the pooled string, check it from psql |
| `relation "chunks" does not exist` | Step 2 skipped or run against a different database | Re-run `schema.sql` against the right one |
| First request after idle is very slow | Render free spins down, Neon free autosuspends | Expected on free tiers; a paid instance removes it |
| Uploads always 429 | Per-session cap reached (5 docs / 3,000 chunks) | Raise `MAX_DOCUMENTS_PER_SESSION`, or run the cleanup workflow |
| Blueprint rejected: `free not a valid plan for service type cron` | Render has no free cron tier | Already fixed — the cleanup is a GitHub Action, not a Render service |
| Answers cite the handbook for your own document | Frontend didn't send `document_id` | Re-upload; scoping is set when the upload completes |

## Rolling back

Render keeps every previous deploy: **service → Events → Rollback**. The
database is unaffected by an application rollback. Nothing in this codebase runs
destructive migrations on boot — `schema.sql` is applied by hand and is
idempotent (`IF NOT EXISTS` throughout).

## After it's live

- Watch the cleanup workflow's runs for the first few nights (GitHub → Actions);
  each run reports how many chunks it removed. If it stops running, the table
  grows without bound. Note GitHub disables scheduled workflows on repositories
  with no activity for 60 days — a commit or a manual run re-enables them.
- `eval/results.json` is the committed baseline. Re-run `python -m eval.run_eval`
  locally after any pipeline change and compare — it holds at 13/13 recall,
  13/13 correct, mean MRR 0.962.
- Every tuning knob (limits, TTL, pool size) is an environment variable listed in
  `.env.example`. Changing one on Render needs only a restart, not a rebuild —
  except the frontend's `VITE_API_BASE`.
