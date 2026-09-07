# RAG Inspector - [Try it out](https://rag-inspector-web.onrender.com/)

A retrieval-augmented generation pipeline over a PDF, built from scratch to actually understand how RAG works, then instrumented so a visitor can see every stage of how an answer was produced, not just the final answer.

Ask a question and you get an answer, but you can also open it up and see how that answer actually got produced. You can look at the embedding step, the two separate searches that run in parallel, the fusion that reconciles them, the reranking that narrows things down, the actual prompt that got sent to the model, and the verification pass that checks the answer against its own context.

# Why this exists

I built this as a summer project, partly to teach myself skills I didn't have yet and partly to have something real for my own portfolio.

The one rule I set myself was not to use LangChain or LlamaIndex. I wanted to write the chunking, the embedding calls, the similarity search, and the prompt construction by hand, all of it. The goal wasn't to get a demo out quickly. It was to get to a point where using a framework would feel like a shortcut for something I already knew how to do myself, rather than trusting a black box I didn't fully understand. Before writing any code, I worked through a full study guide on what RAG actually is and how each part of it works, mainly so I wouldn't end up implementing steps I couldn't explain.

## How it works

```
question
   │
   ├─► embed (voyage-4)  ──► vector search   (pgvector, L2)      ─┐
   │                                                              ├─► RRF fusion ─► rerank (rerank-2.5) ─► top 3
   └──────────────────────► keyword search   (Postgres FTS)      ─┘                                          │
                                                                                                             ▼
                                                              answer ◄── verify (grounded?) ◄── generate (claude-sonnet-5)
                                                                              │
                                                                     not grounded → regenerate once
```

Both searches run over the same chunks and usually disagree. Reciprocal Rank
Fusion throws away their incompatible scores and keeps only rank positions,
so a chunk found by both searches rises above one found by either alone. The
reranker then reads the question and each surviving chunk together, which is
far more accurate and far too slow to run over a whole corpus. Hence
it runs last, on a handful of candidates rather than thousands.

## The build, and what actually happened

# Week 1 — building the first working version

I set up a local FastAPI project with a Postgres database running in Docker, using the pgvector extension to store embeddings. I built two endpoints. The first takes a PDF, pulls the text out of it, splits that text into chunks, sends each chunk to Voyage to get an embedding, and saves the chunk text and its embedding in the database. The second takes a question, embeds it the same way, searches the database for the closest matching chunks, builds a prompt out of those chunks plus the question, and sends that to Claude to get an answer.

I deliberately didn't use LangChain or LlamaIndex for any of this. I wanted to write every step myself so I actually understood what was happening at each stage instead of calling a function that did it for me. Getting the environment properly set up took some trial and error, mostly around how Docker containers handle data, how environment variables get loaded into a Python process, and how Postgres treats the vector type differently from a normal column. None of it was complicated once I understood it, but it took a few passes to get right.

By the end of the week I had a working pipeline. You could upload a document, ask a real question about it, and get an answer that was actually grounded in what you uploaded.

# Week 2 — testing whether retrieval actually held up

My first test document was only a couple of paragraphs long, and it passed every question I asked it. That was itself a problem. The document just wasn't hard enough to expose anything. So I built a fictional company handbook specifically designed to trip up naive retrieval. It had a time off policy that gave different numbers of days depending on when someone was hired, a bonus exclusion mentioned in a section with no link back to where eligibility was originally described, an acronym (EAP) that got used four separate times but only spelled out once, and a policy exception sitting in a completely different section from the general rule it overrode.

Chunk size turned out to matter more than I expected, and there wasn't a single right answer. At 300 words per chunk, a specific fact could get buried inside a long paragraph about something else entirely. At 150 words, that same fact stood out cleanly on its own, but now the smaller chunks sometimes split right through a phrase. The word "PTO" ended up separated from "traditional" at one chunk boundary. "Performance" and "reviews" ended up as the last word of one chunk and the first word of the next.

The keyword half of hybrid search taught me something I hadn't expected. I built it using Postgres's plainto_tsquery, which requires every word in a query to be present in a chunk for it to count as a match. Real questions, phrased the way a person actually asks them, almost never satisfied that condition. I checked this properly by comparing the actual words in each test question against what was in the chunks, and found that only one question out of the whole set was phrased close enough to the source text to get a real keyword hit. This wasn't a sign that hybrid search was broken. It just meant natural questions are bad keyword queries by nature, which is exactly why pairing them with vector search matters.

Reciprocal Rank Fusion turned up two bugs in my own code before it turned up anything interesting in the actual results. One was an off by one error, since enumerate() starts counting at zero and the formula assumes ranks start at one. The other was a scoring mistake that gave partial credit to a chunk that was missing from one of the two lists entirely, when it should have gotten nothing. Once those were fixed, reranking earned its place by fixing a genuine multi hop question, correctly dropping a chunk that only said which policy applied in favor of the chunk that actually gave the number.

# Week 3 — building real evidence

Partway through building this I argued that an LLM judge was pointless. My reasoning was that if retrieval finds the right chunk, generation should always get the answer right, so why bother checking both separately. A counterexample showed up almost right away. A question asking what "EAP" stands for retrieved the correct chunk in first position, with the definition written out in plain text inside it, and the model still answered that the context didn't explicitly state what EAP stands for. Retrieval was correct and generation still failed, and there was no way I would have caught that by only checking which chunk ids came back. That result settled the argument for me.

# Week 4 — adding self verification, and finding its limits

The verification step exists because of the EAP finding. After generating an answer, a second pass checks whether it's actually grounded in what was retrieved, and if not, the system regenerates once. Running the exact same EAP question again confirmed it worked. The flagged answer got replaced with the correct one.

It isn't a clean win everywhere, and I've kept both of the counterexamples I found rather than only writing up the success.

The first is a false positive. One question posed a hypothetical, asking what would happen if an employee was hired in 2017 and is currently on an active PIP. Verification flagged the resulting answer as unsupported, reasoning that the context never confirmed a real employee with that specific hire date. What actually happened is that it mixed up a premise the question was handing to the model with a claim the model was supposedly inventing on its own. That's a real category error, and it's the kind of mistake a strict reading of "stay grounded" can produce.

The second is a retry that didn't fix what it caught. A different question asked whether an Expense Review Committee was involved in performance reviews. Verification correctly noticed that the model had taken a phrase from the PIP process, "in consultation with People Operations," and misapplied it to general performance reviews as well. That's a real and fairly subtle mistake. The retry ran, and came back with the same mistake, just worded differently. The judge still scored the final answer as correct, because the specific fact it was grading wasn't affected by the error. That means the system currently has no way to catch a real, still present inaccuracy that a simple correct or incorrect check doesn't happen to probe.

Both of these are left in on purpose. A single generic retry that just says "look again" is a real mechanism that does work sometimes, and it also has real limits.

# Making it presentable, then making it hold up under real use

A plain upload box with an answer box would have hidden everything described above behind one text field, which is exactly what most beginner RAG projects look like from the outside. Instead the frontend shows the trace directly. You can see the chunk ids and scores from each search, the RRF math behind the fusion, what reranking kept and what it dropped, the actual prompt that got sent to the model, and the verification verdict along with its reasoning.

Pushing this past a personal demo and toward something that could handle real use turned up a second round of real bugs, and these were closer to production failures than learning mistakes.

The AND behavior in plainto_tsquery, the same limitation found during week 2, got rewritten to use OR instead. The same query that used to return zero keyword matches now returns eleven, with the correct chunk ranked first.
Verification occasionally returned JSON that didn't parse, which crashed the whole request. It's now enforced as structured output against a schema instead of being parsed from free text afterward.
Uploading anything past around 128 chunks failed outright, because every chunk was being sent to the embedding API in one call and that's the API's batch limit. Embedding is now batched properly.
A verifier response that got cut off mid JSON because it hit a token limit used to crash the request instead of being handled. Verification now fails open rather than taking the whole request down with it.
PDF pages were being joined together with no separator, which sometimes merged the last word of one page directly into the first word of the next.
Session and document scoping got added after confirming that one browser session could otherwise read another session's uploaded document.
There's now a 50 test unit suite covering chunking, the RRF math, embedding batching, and session validation, none of which spends any API credits to run.

# Current state

Running python -m eval.run_eval against the 13 question golden dataset gives 13 out of 13 on retrieval recall, 13 out of 13 judged correct, and a mean MRR of 0.962. That's the current result after the fixes described above. Several of those 13 questions failed at earlier points along the way, for the specific reasons written up in this README. The eval wasn't put together after the fact to look clean.

# Local setup

Requires Python 3.14, Node 20+, and a Postgres with the pgvector extension.

bash
# 1. Backend dependencies
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt

# 2. Credentials
cp .env.example .env       # then fill in DATABASE_URL and the two API keys

# 3. Database
psql "$DATABASE_URL" -f schema.sql
python -m seed.seed_demo_corpus

# 4. Run
uvicorn app.main:app --reload            # http://localhost:8000
cd frontend && npm install && npm run dev # http://localhost:5173

GET /ready confirms the database is reachable; GET /health only confirms the process is up.

# Tests and evaluation
bash
pytest                  # unit tests, no API calls, no spend
python -m eval.run_eval # full pipeline against the golden questions (spends credits)

The eval scores retrieval (full recall, MRR, per-chunk positions) separately from answer correctness (an LLM judge comparing each generated answer against a written reference). That's deliberate. A system can succeed at one and fail at the other independently, and collapsing them into a single number would hide exactly the kind of gap the EAP finding depended on noticing. Results are written to eval/results.json.

# Deployment

Backend on Render (Docker), Postgres on Neon, frontend as a Render static site. render.yaml describes all three plus the nightly session-cleanup cron. Every secret is sync: false and set directly in the dashboard, never committed.

See DEPLOYMENT.md for the full runbook and the pre-deployment audit record, including what was wrong, why each fix mattered, and how it was verified.

# Layout
Path	What's in it
app/config.py	Every environment variable and limit, validated at startup
app/routes/documents.py	The two endpoints, with validation and rate limits
app/services/pipeline.py	Orchestration and the stage-by-stage trace
app/services/storage.py	Pooled Postgres access, hybrid search, RRF
app/services/embedding.py	Voyage embedding (batched) and reranking
app/services/generation.py	Claude calls, structured output, error mapping
eval/	Golden dataset, scoring, LLM judge
seed/	Demo corpus loader and the session cleanup job
frontend/src/components/	Hero, the walkthrough scenes, upload, charts