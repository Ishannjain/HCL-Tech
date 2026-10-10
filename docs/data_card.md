# Synthetic retail data card

The dataset exercises authorized order lookup, return boundaries, refunds, warranties, ambiguity, and untrusted order notes. It contains 30 synthetic customers, 20 products in five categories, 60 orders, 60 order items, and nine return records. No original email or phone fields are loaded into runtime SQLite.

The user supplied the original synthetic CSVs, whose rows were marked synthetic. Their original generating model and prompts were not provided. Current schema migration and fixture edits are deterministic Python transformations. They must not be represented as a completed LLM-generation provenance record. `scripts/generate_data.py` can create a separate NIM-generated kit and save exact prompts and model information once the API key is configured.

On 2026-10-10, a separate kit was generated with the live `nvidia/nemotron-3-super-120b-a12b` model and passed schema/reference/value validation. It contains 30 customers, 20 products, 60 orders, 62 order items and eight returns. Exact prompts, token usage and the empty violations list are recorded in `data/nim_generated/generation_record.json`. This preserves the working demo's curated edge fixtures. The generated kit has not been substituted into the runtime or independently reviewed for every scenario boundary.

`scripts/validate_data.py` checks the Annex C columns, IDs, enum values, unique keys, references, quantities, price bounds, dates, delivery status, and reserved judge identifiers. Actual output is in `docs/data_validation.json`. The importer is transactional and rejects duplicates rather than silently overwriting records.

Customers are assigned evenly across STANDARD, GOLD, and PLATINUM. Products retain the supplied LAPTOP, MOBILE, AUDIO, APPLIANCE, and TELEVISION categories. Exact identifier mappings and assigned fields are in `docs/data_conversion.json`. `docs/fixture_map.json` identifies the last-day, one-day-late, high-value, discounted, non-returnable, undelivered, existing-return, repeat-purchase, warranty, and injection fixtures. Their fixed as-of date is 2026-10-10.

The dataset covers a limited electronics corpus and is not representative of a real retailer's customers, geography, product distributions, or claim outcomes. Quality-check and inventory booleans are fictional verified fixture data. Policies and operational conditions still need human review. There is no real customer database or payment integration.
