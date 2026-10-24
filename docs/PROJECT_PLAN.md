# Tajrubin Travel AI — Delivery Plan v1.0

**Owner:** Tajrubin Travel AI community · **Updated:** 2026-10-24 · **Status:** In progress (Sprint 01)

**Mission:** Create an open-source, privacy-conscious AI travel companion that converts a simple natural-language request into a **source-attributed, realistic and editable** trip. Start with reliable Iran knowledge and expand via country-specific knowledge packs. Keep the production Tajrubin marketplace backend and all proprietary assets separate.

## Product promise

1. Ask naturally; no prompt expertise or long forms.
2. Discover places and local experiences using attributable knowledge.
3. Build a multi-day plan that obeys opening hours, travel time, budget and accessibility constraints **when verified data is available**.
4. Review as cards, timeline and map; change one stop without destroying the remainder of the trip.
5. Clearly label source, freshness, estimates, missing evidence and unsupported real-time claims.

## Personas

- **Traveler:** wants an understandable, adaptable travel plan from mobile.
- **Developer:** wants a documented, reproducible local install and clean extensibility.
- **Travel company (later):** wants an API/SDK without receiving private marketplace code.

## Beta scope

**P0:** typed traveler intent; local knowledge ingestion; retrieval with provenance; abstention on insufficient evidence; planning constraints; partial replanning; responsive bilingual UI (Persian/English); map presentation; comprehensive automated evaluations and security safeguards.

**P1:** save trips; share/export; persistent preferences with consent; feedback dashboard; provider selection and latency optimization.

**Excluded until later:** purchasing/reserving autonomously, invented live hours/prices/availability, unlimited external tool execution, worldwide coverage, continuous location tracking.

## Current repository baseline (read-only inspection)

- **Existing:** Python package; Pydantic knowledge contracts and markdown loader; deterministic lexical retriever and context formatter; OpenAI-compatible/local model adapters; 9 test modules; GitHub Actions security workflow with pytest, Bandit, pip-audit and detect-secrets; Tehran example document.
- **Not yet verified:** full CI health, test coverage, exact dependency vulnerability status and historical secret scan.
- **Missing from inspected main tree:** complete agent orchestrator, public web demo, route feasibility optimizer and public project license.
- **Important:** the published repository is not the same as the private tajrubin-ai-core backend.

## Architecture (logical components)

Web UI → safe API boundary → Agent Orchestrator (bounded steps/time/budget) → Intent Parser → Knowledge Retriever (lexical baseline, later hybrid) → Answer/Planning/Partial-Replan Engines → Feasibility + Evidence Validation → Typed Response. Cross-cutting: user-consent memory, trace/metrics, access control, secret hygiene, human approval gates. Avoid autonomous multi-agent complexity until tests justify it.

## Milestones / dependencies

| Milestone | Deliverable | Exit gate |
|---|---|---|
| M0 / Sprint 01 | Baseline, reproducibility, QA slice, security hardening, public docs | All required CI checks pass, current tests verified, no critical/high known vulnerabilities |
| M1 | Traveler intent + provenance-aware retrieval + Iran destination knowledge | Gold-set retrieval/intent evaluation and citations pass |
| M2 | Deterministic itinerary + partial replanning + constraints | No impossible hard-constraint violations in acceptance cases |
| M3 | Mobile-first bilingual web, cards/map/timeline, safe save/edit | End-to-end traveler journey works without developer assistance |
| M4 | Quality, observability, privacy, threat-model, cost/load benchmarking | Meets public beta quality thresholds |
| M5 | Live demo, onboarding, open-source governance, brand and GTM | Installation reproducible; meaningful feedback and analytics available |

## Measurable beta targets (not current performance)

- ≥90% gold-set task success, ≥95% feasible plans, 0 known critical/high release-blocking security findings.
- User can enter a prompt within ≤2 actions.
- Model outputs that lack reliable evidence are labeled uncertain or abstain.
- Define response-time/cost SLOs only after recording baseline measurements.

## Sprint 01 work packages

1. **S01-01 / Baseline:** record commit, Python version, fresh install, test count/pass/fail, CI run status and dependency scan; document deviations.
2. **S01-02 / Thin QA Slice:** strictly validated natural-language question → knowledge retrieval → attributed provisional summary or explicit insufficient-evidence response; tests for both.
3. **S01-03 / Security:** review URL/SSRF policy at input boundaries, prompt injection, log redaction, provider budgets, Git history secrets and workflow rules; prohibit copying secrets or proprietary artifacts.
4. **S01-04 / Documentation:** realistic README, contribution guide, install/run/demo guide, architecture and data provenance docs; choose license only after owner approval.
5. **S01-05 / Evaluation:** versioned offline benchmark cases and scoring for intent, retrieval, provenance, constraints and refusals, with CI regression gates.

## Work policy

- Make changes on feature/planning branches; submit PRs, pass tests, review before merging to main.
- Do not invent test success, price or source validity.
- Do not import private Tajrubin implementation, real user information, credentials or confidential prompts.
- Every new module requires contract tests, negative tests, error handling and documented assumptions.
- Seek approval before publishing an open-source license or enabling paid external services.

## Marketing workstream (after a usable demo)

Create a 60-second demo, a clear landing page, installation guide, open-source comparison benchmarks, architecture explainer, technical blog posts, destination case studies and GitHub showcase. Track sign-up→first-plan completion, returning planners, issues/stars/contributors and feedback. Prioritize real user success over vanity metrics.

## Immediate next gate

Complete Sprint 01 issues; keep main untouched until tests and reviews are complete. All scope additions must preserve the user promise: *deep intelligence, extremely simple interface*.
