# Resource construction contracts

The schema and 27 Distribution vocabulary entries are copied from the clean
companion `data-api` checkout at `1cabc73851220926a9359b5e549bf30d2710cb12`:

- `mkdocs/docs/v1/ld/schemas/ogm-aardvark-btaa.schema.json`
- `backend/db/migrations/create_distribution_types_table.py`
- Resource columns in `app/resources/models.py` derive from `backend/db/models.py`.

Upstream schema SHA-256: `c9ba3911d5b58905de4696ee260af1172fe8b117c39759afc8469f415b6ec7e3`.
The vendored JSON normalizes trailing whitespace. The local construction migration retains the 84 named compatibility columns,
adds administrative identity/control columns, and freezes the Distribution
vocabulary including its noncontiguous IDs. It is a fresh local schema based on
source declarations, not a reconciled migration of the existing production
catalog. DEC-005 remains the authority for production types, constraints,
triggers, downstream envelopes, and before/after reconciliation.

Draft import validates input types against these Resource columns and reports
missing required schema properties and enum differences. It is not a complete
JSON Schema/publication validator. Incomplete legacy metadata may be saved as a
draft with evidence; it is not certified for public delivery.
