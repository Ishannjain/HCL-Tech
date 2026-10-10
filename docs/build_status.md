# Verified build status — 2026-10-10

Project folder: `C:\Users\Mohit\Downloads\Hacathon Project\retail-support-agent`.

The API and chatbot UI are running in Docker at http://127.0.0.1:8000/docs and http://127.0.0.1:8501/. Both Compose services passed their HTTP health checks. Docker Desktop 4.94.0, engine 29.8.2 and WSL 2.7.13.0 were installed and verified. A stale Secrets Engine socket directory prevented Desktop startup; it was preserved as `C:\Users\Mohit\AppData\Local\docker-secrets-engine.backup-20261010-1`, after which the engine started. No Docker storage reset was performed.

The provided NVIDIA endpoint is configured through the ignored `.env` file, using `nvidia/nemotron-3-super-120b-a12b`. A live connection probe and Docker-hosted refund and warranty requests succeeded. The refund fixture returned INR 2,312.40 from 2,636.00 less 263.60 and 60.00. This is an estimate; no payment was issued. API keys are excluded from Git and Docker build context.

Validation completed:

- 43 automated tests passed, including ownership isolation, source precedence, exact refund/date boundaries, prompt injection, idempotent return writes, two-account sign-in, session identity binding, expiry and logout revocation.
- 28 labeled live NIM/Chroma evaluation cases passed their answer contracts and independently specified tool assertions. Expected citation reference match and abstention accuracy were 100%; retrieval hit rate was 92.86%. Median latency was 902.40 ms and p95 was 3,005.27 ms in that measured run. These are scoped sample results, not a guarantee of every possible question or semantic citation correctness.
- The working dataset passed validation: 30 customers, 20 products, 60 orders, 60 items and nine returns.
- A separate live NIM-generated kit passed schema/reference/value validation: 30 customers, 20 products, 60 orders, 62 items and eight returns, with three customer tiers and five categories. Five model calls used 34,693 tokens. Exact prompts and model provenance are retained in its generation record. It does not replace the curated runtime fixtures.
- UI refund, warranty policy, order and eligibility presentation uses readable messages, separated paragraphs, formatted amounts and expandable source/trace details. Financial values come directly from deterministic tool results.

Run `./Start-Docker.ps1` from the project folder to start the services again. The first image build downloads dependencies; subsequent builds use Docker's cache. SQLite and Chroma remain in the mounted `runtime` directory. A pre-container SQLite/Chroma backup is in `work/runtime_windows_backup`.

Customer login is now available in the UI: `customer1` / `Customer1@123` maps to C1001, and `customer2` / `Customer2@123` maps to C1002. These are deliberately public fictional demo accounts. The UI fixes customer identity after sign-in and clears all conversation/account state on sign-out. Server sessions expire after eight hours and are revoked on logout; stored passwords use salted scrypt hashes. Docker-hosted login, customer-header mismatch rejection and logout revocation checks passed for both accounts. The trusted judge header API contract remains available without bearer authentication, as documented in the README; this does not replace a production authentication gateway.

Before submission: review semantic claim-to-clause support and generated scenario coverage, fill actual team contributions, review the AI disclosure, and have each member sign their own declaration. The guide mandates Ollama as primary, while this implementation uses NIM at the user's request; organizer acceptance is needed for that stack deviation. Scanned PDFs require supplied OCR text, and other documented interpretation limits remain in the README. Real authentication, manufacturer claim verification and payment execution are outside this synthetic hackathon demo.
