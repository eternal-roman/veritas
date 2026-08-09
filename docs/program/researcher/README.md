# Researcher inbox

Runtime reports are written under `docs/program/researcher/inbox/` by
`python -m veritas.researcher` / `BlockBoard.write_inbox`.

That directory is **gitignored** — do not commit tick artifacts (absolute paths,
machine-local thrash). Agents read inbox on next tick from local disk only.
