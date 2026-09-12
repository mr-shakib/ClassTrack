# Vendored from open-routine

These five files are copied verbatim from
`/home/mr-nacht/Workspace/Personal/projects/open-routine` at commit **`bcd2b8d`**
(2026-08-30), with one mechanical change: `open_routine.ingestion` →
`classtrack.routine`, `open_routine` → `classtrack`.

| File | Lines | Purpose |
|---|---|---|
| `lattice.py` | 138 | DAYS/SLOTS constants, day+slot normalisation, `slot_bounds()` |
| `pdf_reader.py` | 230 | pdfplumber grid walk → `RawCell` |
| `cell_parser.py` | 168 | `"CSE414(62_E1)"` → course / batch / section / lab / optional |
| `normalizer.py` | 94 | Room and initial cleanup |
| `pipeline.py` | 235 | Full ingest with atomic activation swap |

`models/routine.py` and `models/teacher.py` are vendored from the same commit.

## Why vendored rather than imported

`open-routine` is a separate repository with its own release cycle. Copying five
stable files avoids cross-repo coupling. To pull upstream fixes, diff against
that commit and re-apply the import rename.

## Do not "fix" the lattice

`time_slot` is a **lattice coordinate compared with `==`**, not a time. Classes
snap to a fixed 6×6 grid and can never partially overlap, which is why conflict
detection elsewhere in ClassTrack is three indexed equality lookups rather than
interval arithmetic. `start_min` / `end_min` exist for display and sorting only.

Replacing slot-label equality with time-range overlap logic is the most tempting
and most damaging refactor available in this codebase.

## Status

The PDF path is unchanged from upstream and is exercised by open-routine's own
tests. It has **not** been run against a real DIU routine PDF in this project —
no such document is in the repo, and upstream deliberately does not redistribute
it. Use `classtrack ingest <file.pdf>` to exercise it; `classtrack demo-routine`
synthesises an equivalent routine when no PDF is available.
