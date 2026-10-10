# Retail support agent

This hackathon project answers retail policy questions from sourced documents and uses deterministic SQLite tools for orders, return eligibility, refund estimates, and warranty periods. It uses a bounded LangGraph workflow, persisted Chroma embeddings, FastAPI, and Streamlit. The selected language provider is NVIDIA NIM.

The checked-in dataset is synthetic. Croma policy snapshots are combined with exactly three clearly marked synthetic hackathon documents. Demo fees, approval thresholds, non-returnable AUDIO category, warranty-date conventions, and a mock AUDIO circular are not claims about Croma's actual policies.

## Current verification

See `docs/build_status.md` and `evaluation/reports/` for measured results. Mock evaluation verifies contracts and deterministic tools; it does not establish real NIM answer quality. The project has a real NIM client, but live evaluation requires your API key. Do not describe mock results as provider-backed results.

## Windows setup

Open PowerShell in this folder. The `.venv` and `.env` have been created on the current computer; for a fresh checkout create them as follows:

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally and add `NVIDIA_API_KEY`. Set `MOCK_LLM=false` to use NIM. Set a long random `ADMIN_API_KEY` for document ingestion and privileged audit access. Never commit `.env` or display its contents. The configured default is:

```text
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/nemotron-3-super-120b-a12b
RETRIEVAL_BACKEND=chroma
```

Bootstrap once; reruns preserve customer records and skip already active source IDs:

```powershell
& .\.venv\Scripts\python.exe -m scripts.bootstrap
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
& .\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501. API docs are at http://127.0.0.1:8000/docs. The first Chroma bootstrap downloads the sentence-transformers embedding model; it never downloads a local language model. Later restarts reuse the persisted index. `RETRIEVAL_BACKEND=keyword` is an explicitly labeled lightweight test mode and does not satisfy the mandatory Chroma stack by itself.

## Demo customer login

The chatbot opens with a sign-in form. Use `customer1` / `Customer1@123` for C1001, or `customer2` / `Customer2@123` for C1002. These deliberately public, fictional demo credentials are not production accounts. The signed-in customer is fixed; signing out revokes the session and clears the conversation and account state. Passwords are stored as salted scrypt hashes, and server-side bearer sessions expire after eight hours. No passwords or tokens are logged by the application.

`POST /auth/login`, `GET /auth/me` and `POST /auth/logout` support this UI flow. When a bearer session is supplied, `/ask`, `/audit` and `/returns` reject a mismatching customer header. The use-case's direct `X-Customer-Id` contract remains available for trusted judge clients. This localhost demo is not a production authentication gateway; a deployment must enforce authentication for those direct API clients and replace public demo credentials.

## Docker startup

On Windows, run `./Start-Docker.ps1` from the project folder. It finds Docker's installed CLI, starts Desktop, and waits for the API and UI to become healthy. Stop any manually started API/UI servers before using the same ports in Docker.

With Docker available and `.env` configured:

```powershell
docker compose up --build
```

Both services share the built image. SQLite and Chroma are embedded stores persisted under the mounted runtime directory. The API bootstraps before startup; the UI waits for API readiness. The UI's default API address inside Compose is `http://api:8000`. Bindings are restricted to localhost. Docker execution must be verified on a machine with Docker; writing a Compose file is not proof of a successful container run.

The Windows environment's exact installed versions are recorded in `requirements.lock.txt`, and the verified Linux image's versions in `requirements.docker.lock.txt`. `requirements.txt` is the portable bounded dependency list; Docker preinstalls CPU PyTorch so embedding dependencies do not pull CUDA packages.

## API examples

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/sources
curl.exe -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -H "X-Customer-Id: C1001" --data '{"question":"How much refund for defective item O-100051 SKU-0001?","as_of_date":"2026-10-10"}'
```

`GET /audit/{trace_id}` requires the customer's `X-Customer-Id` or a valid `X-Admin-Key`. General-question audits with no owner require the admin key. `X-Customer-Id` is a trusted-context simulation required by the guide; it is not production login authentication. Use a server-authenticated gateway before serving real users.

`POST /ingest` is multipart with `file`, `metadata` containing Annex B JSON, and optional `rules` containing a JSON list. The endpoint requires `X-Admin-Key`; judges can use the admin ingestion panel without putting keys in curl command history. Example metadata and document are in `data/live_demo/`. Upload `new_window.md` with `metadata.json` and no rules payload to test numeric extraction. For structured rules see `data/rules/seed_rules.json`.

`POST /returns` is an additional customer-authorized endpoint. Body: `order_id`, `sku`, `reason`, and `idempotency_key`. It rechecks eligibility inside a write transaction, creates a request, and records approval when needed. It never issues a payment. `/ask` is read-only, including what-if requests.

## Judge data import

```powershell
& .\.venv\Scripts\python.exe -m scripts.load_data --dir test_customers
```

The directory must contain `customers.csv`, `products.csv`, `orders.csv`, `order_items.csv`, and `returns.csv` with Annex C headers. Empty tables can be header-only files. Optional `order_facts.csv` supplies verified boolean fixtures for quality checks and inventory; absent facts produce clarification rather than fabricated approval. Judge identifiers are permitted by the loader. Duplicates are rejected and the whole import rolls back; use fresh judge IDs rather than silently replacing existing data.

Team dataset validation rejects reserved judge identifiers:

```powershell
& .\.venv\Scripts\python.exe -m scripts.validate_data --dir data/synthetic --output docs/data_validation.json
```

Original CSVs are preserved in `data/original/`, and original document text in `data/original_documents/`. `docs/data_conversion.json` records renamed identifiers, assigned fields, and fixture edits. The legacy evaluation suggestions are retained in `data/samples/`; the executable labeled set is `evaluation/questions.jsonl`.

## Tests and evaluation

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m evaluation.run_evaluation --backend chroma --output evaluation/reports/chroma_mock_report.json
& .\.venv\Scripts\python.exe -m evaluation.compare_configs
# After configuring the key and testing provider access:
& .\.venv\Scripts\python.exe -m evaluation.run_evaluation --live --backend chroma --output evaluation/reports/nim_live_report.json
```

Evaluation uses a separate database and fixed scenario dates, so it does not change demo orders. It measures exact answer types, independently specified tool values, expected citation reference matches, retrieval hits, abstention, latency, calls, and tokens. Semantic claim-to-clause citation correctness and general procedure quality still need human review. A matching document ID alone is not proof of every claim. Mock measurements have zero model calls and must remain labeled.

Optional real NIM data generation:

```powershell
& .\.venv\Scripts\python.exe -m scripts.generate_data --out data/nim_generated
```

The generator records exact prompts, provider model, tokens, and validation. It preserves the current dataset and refuses nonempty output folders. The original dataset's generating model and prompts were not supplied; do not invent that provenance. Generate and validate the new kit, review boundary coverage, and update the data card before claiming the guide's LLM-generation deliverable is complete.

## Design and known limitations

- Policy precedence and business thresholds are shared by policy answers and tools. Rules link to exact source evidence. Scope/date filtering happens before supersession, authority, and recency. Ties with different values are flagged.
- Generic document answers quote exact selected evidence rather than allowing the LLM to invent factual prose. Policy-window answers and tool results are assembled from resolved rules. Procedure formatting is deliberately conservative.
- Numeric live extraction supports unambiguous return windows, restocking percentages, reverse-shipping amounts, and approval limits. More complex rule semantics need a validated structured rules payload. Unsupported rule kinds are reported; they are not silently interpreted.
- Formats supported: TXT, Markdown, searchable PDF, and DOCX. Scanned PDFs need an OCR-produced searchable PDF or supplied extraction. DOCX physical pagination is not reconstructed; citations use section names and extraction page 1. Images and complex table layouts require review.
- Croma snapshots do not publish reliable version or effective dates in the supplied files. `snapshot-2026-10-10` and that observation date bound demo applicability, not an invented historical policy date. Historical questions before the snapshot abstain.
- MOBILE damage reports use a 48-hour clause, but the mandatory order schema has only dates. The tool asks for support verification instead of pretending date-only data proves the hour boundary.
- Warranty tools report the synthetic recorded period. They do not certify manufacturer coverage, installation, exclusions, or a real claim.
- Partial-quantity returns and unresolved policy interpretations require support clarification. No payment processor or actual human approval dashboard is connected.
- SQLite publication makes source chunks and registry rows visible together. Chroma indexing is staged before publication; failed SQL publication removes the indexed generation. A process crash can leave unreferenced vector chunks, which are excluded by active SQLite source IDs. See the recovery script.
- NIM replaces mandatory Ollama at the user's request. The guide permits cloud inference only as fallback. Disclose the deviation and obtain organizer acceptance for full stack compliance.

Architecture: `Streamlit → FastAPI → LangGraph → source retrieval / rule resolver / deterministic tools → Chroma + SQLite`. See `docs/architecture.md`.

Live NIM evaluation and a separate validated NIM-generated kit are recorded. Before the final submission, review human citation support and generated boundary coverage, obtain organizer acceptance for the NIM stack deviation, complete team contributions and AI disclosure review, and have every member sign their own declaration. No signatures or member commits have been fabricated. Container verification is recorded in `docs/build_status.md`.
