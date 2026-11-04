# Knowledge base (RAG)

Real documents only. **Numbers about current risk never go here** — the agent reads them live from SQL Server.

| Folder | What to put | Status |
|---|---|---|
| `safety_guidelines/` | Official/civil-protection safety guidance | ✅ general starter guidance (verify before production) |
| `wadi_descriptions/` | One file per wadi/region: geography, catchment, known flood behaviour | ⬜ **team to add** from real sources |
| `past_flood_reports/` | One file per documented flood event | ⬜ **team to add** from real sources |

Rules
- Markdown (`.md`). Start with front-matter: `title`, `doc_type`, `language` (`ar`/`en`), `origin` (source + date/URL).
- Do **not** invent facts. If you can't cite a source, don't add the file.
- Files starting with `_` (templates) and this README are not indexed.
- After adding/changing files run: `python -m genai.vector_store_setup`
