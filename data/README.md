# data/

Reserved for datasets. **Large/raw data must NOT be committed to git** (see `.gitignore`).

- `raw/` — downloaded/unprocessed source data (satellite scenes, CSVs, GeoJSON).
- `processed/` — cleaned/derived datasets produced by the pipeline.
- `sample/` — small representative samples for development and demos.

Add a `.gitkeep`-only folder until real data handling begins (Phase 4 and later).