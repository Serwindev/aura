# 001 — Development environment: SQLite for dev, cloud STT only, no Docker

- **Date:** 2026-11-07 · **Status:** accepted (human, 2026-11-07)

## Context
The dev laptop has an AMD integrated GPU (no NVIDIA/CUDA), 7 GB RAM, and no Docker.
`context.md` §3 assumed a local RTX-class GPU for self-hosting IndicConformer.

## Options
1. PostgreSQL in Docker (plan v2.0 default) — heavy next to an Android build on 7 GB RAM.
2. SQLite for dev/demo via SQLAlchemy; PostgreSQL remains the production target.

## Choice
- **D-13:** SQLite for development and the demo; code stays PostgreSQL-ready (SQLAlchemy 2 + Alembic). Swap = `DATABASE_URL` change + migration test.
- **D-14:** Self-hosted IndicConformer is out of the bake-off on this machine (no CUDA; CPU inference of a 600M model on 7 GB RAM is impractical). STT candidates: Sarvam, Bhashini. Revisit if a GPU machine becomes available.

## Consequences
- R-08 mitigation "local IndicConformer first if keys are late" no longer holds → until keys arrive, the pipeline runs on clearly labelled **mock** providers.
- `make` is not available on Windows → `make.ps1` mirrors the Makefile; CI uses the Makefile on Linux.
