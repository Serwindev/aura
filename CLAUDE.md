# A.U.R.A. — instructions for Claude Code

Voice-first assistant for ASHA workers: speak a visit note → structured record → she confirms once → reuse for tasks, reports and guided data entry.

## Read order
1. `handoff.md` — current state, next actions, blockers, working agreement (read fully, every session).
2. `plan.md` — scope, architecture, backlog (task IDs `T-xxx`), gates. Read only the sections the task needs.
3. `context.md` — verified facts, programme rules, sources. Facts are tagged [V] verified / [U] unverified / [D] decision. Never build on [U] without checking.

## Non-negotiables
- Synthetic data only. No real patient names, IDs, or recordings.
- Privacy contract: no GPS/location, contacts, call logs, SMS, other-app monitoring, attendance, or productivity scoring. Permissions: microphone and notifications only.
- LLM output is untrusted: validate in code, require evidence quotes, null when not stated, human confirms; never auto-submit.
- Never claim government integration we do not have. No scraping, JS injection, Accessibility autofill, or storing government credentials. Simulated pieces are labelled `SIMULATED`.
- Clinical rules live in `rules/*.yaml` with a source and review status; the app is advisory only.
- No numbers on slides or in docs without a file in `eval/results/` or a cited source.
- Plan before code; ask when a decision is open; run tests and show real output; update `handoff.md` at the end of every session.
- Be token-efficient: targeted reads, short summaries.
