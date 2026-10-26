# Match Stats — Design

Date: 2026-10-26
Status: approved by the user on 2026-10-26

This document covers two things, built in this order:

1. **The product**: a web page to analyze any two football teams before a match, for betting.
2. **The development workflow**: Opus orchestrates, Haiku 5.5 workers implement in parallel, each visible in its own Herdr pane.

Items marked **(builder's call)** were filled in by the designer, not requested by the user, and may be changed.

---

## Part 1 — The product

### Intent

The user bets on Betano, mostly on matches from the top 5 European leagues. Today, before a match, they check each team's recent matches across different websites. They want one page where they pick two teams and get a complete analysis: probabilities per market, backed by the stats that explain them.

### Goals

- Pick any home team and away team from the top 5 leagues and get a full analysis instantly.
- Home page lists **today's matches** (top 5 leagues) with the analysis precomputed.
- Show probabilities per market: 1X2, goals over/under 2.5, BTTS, corners, cards, shots, and shots on target.
- Show the evidence behind the numbers:
  - **Season stats** for both teams side by side.
  - **Last 6 matches** of each team.
  - **Head to head**: last meetings between the two teams.
- Works on the user's PC and phone, from anywhere, without the PC being on.
- Data refreshed **once per day, overnight**. This freshness is explicitly enough for the user.

### Non-goals (for v1)

- **No comparison against bookmaker odds.** The user compares probabilities with Betano odds themselves. Possible future feature (manual odds entry or an odds API).
- **No leagues beyond the top 5.** Champions League, Europa League, cups and other leagues are deferred. The data layer must make adding a league cheap; cross-league competitions (CL) need cross-league strength rating and are explicitly a later project.
- No live/in-play data, no confirmed lineups, no on-demand fetching when picking teams.
- No user accounts, no login.
- No scraping of Betano or any bookmaker.

### Anti-goals

- A page that shows probabilities without the evidence behind them.
- Anything that costs money to run or needs a server the user must maintain.
- Presenting probabilities as guarantees. The page should not imply a model reliably beats the market.

### Constraints

- Free data sources only.
- Zero hosting cost.
- Must be usable on a phone screen (single column).
- Generated artifacts (code, UI copy, docs) in English.

### Approaches considered

| # | Approach | Trade-off |
|---|----------|-----------|
| 1 | Python + FastAPI + HTMX on the user's PC, phone via Tailscale | Simple and free, but no page when the PC is off |
| 2 | Streamlit (Streamlit Cloud) | Fastest to build; rigid UI, mediocre on mobile, poor architecture |
| **3** | **Nightly batch job (GitHub Actions) → static JSON → static site computing probabilities in the browser** | **Free, available anywhere, no server; data is from the last overnight run** |
| 4 | FastAPI + Postgres backend, React/Next frontend | Cleanest separation, but double the project and needs a paid/always-on server |
| 5 | Full TypeScript (Next.js + Postgres) | One language, but fights the Python football-data ecosystem |

**Chosen: 3.** The user confirmed that data from the overnight update is enough, so on-demand fetching (which would require a server) is not needed. It covers PC and phone at zero cost and zero maintenance.

### Stack (proposed by designer, confirmed by user)

- **Data + model**: Python, pytest. SQLite as working storage inside the job.
- **Nightly job**: GitHub Actions, scheduled ~04:00 (Europe/Madrid). Produces JSON files.
- **Site**: Astro + TypeScript, static output. Probability calculation runs client-side from precomputed team parameters.
- **Hosting**: Vercel or Netlify free tier **(builder's call which one)**.
- **Publishing (user)**: the nightly job **commits the generated JSON to the repo automatically every day**; that commit triggers the site redeploy. This automated commit is the only push not made by a human.
- **User-only steps** (the plan must stop and ask for them): create the GitHub repo under the user's account, link it to the hosting provider, and grant the Actions workflow write permission to the repo.

### Data sources

- **football-data.co.uk** (main source): per-match results, shots (`HS/AS`), shots on target (`HST/AST`), corners (`HC/AC`), fouls, yellow/red cards (`HY/AY/HR/AR`) for the top 5 leagues and their second divisions (E1, SP2, I2, D2, F2), many seasons back. Also publishes an upcoming-fixtures file, usable for "today's matches".
- **Understat**: per-match xG / xGA for the top 5 leagues.
- Team name matching between sources is required (e.g. "Man United" vs "Manchester United"). **(builder's call: a maintained alias table, tested.)**
- football-data.co.uk's fixtures file is not updated every day. When today's fixtures are missing or stale, the home page shows an explicit "no fixtures data for today" state and the team pickers keep working. Adding a second free fixtures source is optional **(builder's call)**.
- If a source fails during the nightly run, the job must keep the previous day's JSON published rather than publishing broken or empty data **(builder's call)**.

### The model **(builder's call, all of it)**

- **Goals**: Poisson-based model with team attack strength, defense strength and home advantage, fitted per league on recent seasons with time decay (Dixon-Coles style). Gives 1X2, over/under 2.5 and BTTS from the score matrix.
- **Corners, cards, shots, shots on target**: per-team "for" and "against" rates (home/away), adjusted by opponent, modeled as Poisson or negative binomial. Market lines shown: corners 9.5, cards 4.5, shots 24.5, shots on target 8.5 as defaults. **(builder's call whether lines are fixed or the user can change them.)**
- **Settlement rules (user, matching Betano)** — the model must predict exactly what Betano settles on:
  - Corners, cards, shots and shots on target markets are **match totals** (both teams combined).
  - **Shots** and **shots on target** are separate markets. A shot on target also counts as a shot (total shots include shots on target).
  - **Cards: yellow = 1, red = 2.** The builder must check how football-data.co.uk records a second yellow (in `HY`, `HR`, or both) so it is not double-counted or missed, and document the decision.
- The nightly job outputs each team's fitted parameters; the browser combines two teams' parameters to compute any pairing.
- The model must have a backtest on past seasons (e.g. log-loss / calibration) so we know whether its probabilities are sane. No target number is set.

### The page (layout "A", validated with mockups)

Single column, markets first, evidence below.

**Home**
- Header with "Today" and "Compare teams".
- League selector + home team / away team pickers + "Analyze" button. **Both teams must be from the same league in v1 (builder's call)**: the model is fitted per league, and cross-league pairings are the same problem as the deferred Champions League work.
- "Today · updated HH:MM" list of today's matches with a preview of key probabilities; tapping opens the analysis.

**Analysis page**
1. **Markets** — cards: 1X2, goals O2.5, BTTS, corners O9.5, cards O4.5, shots O24.5, shots on target O8.5.
   - **Per-team markets (user)**: for goals, corners, cards, shots and shots on target, each team's own total also gets a probability (e.g. "Barcelona shots on target over 4.5: 62%"), alongside the match total, plus that team's expected value for the stat. Per-team default lines are the builder's call.
2. **Season stats (current season), side by side**: position · points, W-D-L, goals for/against per match, xG/xGA per match, **shots for/against** and **shots on target for/against** (separate rows, requested by the user), corners for/against, yellow/red cards, BTTS % and over 2.5 %, clean sheets. Toggle: all / home only / away only.
3. **Last 6 matches of each team**: result, opponent, home/away, score, xG, shots, shots on target, corners, cards.
4. **Head to head**: all past meetings available, including when a team was in another division; summary over the last 6 (wins, draws, average goals, BTTS count).

Mockups: `.superpowers/brainstorm/*/content/layout-v3.html`.

### Left to the builder

- Exact JSON schema and file layout.
- Hosting provider (Vercel vs Netlify).
- Visual design beyond the validated layout.
- Number of past seasons used for fitting and for head to head.
- How "current season" is handled in the first weeks of a season (few matches).

---

## Part 2 — The development workflow

### Intent

The user wants development to run as: **Opus plans and reviews, Haiku 5.5 workers write the code**, several workers at once, each visibly running in its own Herdr pane. The user only watches; they don't type into workers.

### Decided by the user

- Opus (orchestrator) splits plans so **several workers work at the same time**, as efficiently as possible, not one at a time.
- Each worker runs in its own Herdr pane.
- The user watches only; Opus reviews each result when the worker finishes.
- Workers get **broad permissions** (no approval prompts).

### How it works (designer's proposal)

- **Waves**: the plan groups independent tasks into waves. All tasks in a wave run in parallel; the next wave starts when the previous one is merged. Tasks in the same wave must not depend on each other.
- **Isolation**: each worker gets its own git worktree and branch (Herdr has worktree support). Workers never share a working tree.
- **Worker = separate Claude Code process** running `claude-haiku-5-5` inside a Herdr pane, started by Opus with a task prompt that references the plan task. It runs in **interactive mode with the task as its initial prompt** (not `claude -p`, which shows nothing until it finishes), so the user can watch it work live. The user does not type into it. **(designer's call)** Normal in-process subagents are not used for implementation because they are not visible in panes.
- **Completion**: Opus waits on Herdr's agent state (done/idle) instead of polling by hand.
- **Review**: Opus reads the worker's diff, runs the tests, and merges the branch if it is correct. If not, it sends one round of corrections back to a worker. If still wrong, Opus reports it to the user.
- **Concurrency cap**: at most 4 workers at once, to stay within plan usage limits. **(designer's call)**
- **Guardrails on broad permissions** **(designer's call)**: workers cannot `git push` or touch remotes; cannot write outside their worktree; cannot install system software (project-level dependencies only).
- **Project rule (user)**: the user's global `CLAUDE.md` tells the orchestrator to write code itself and delegate only in narrow cases, and adds feature-document tracking (ODD), the gentle-ai review/consent gate after commits, and delegation limits. In this project a project-level `CLAUDE.md` overrides all of that:
  - Opus plans and reviews; Haiku workers implement via Herdr panes.
  - **Opus's review of each worker's result replaces** ODD tracking documents and the gentle-ai review/consent gate.
  - **Engram stays active** for the orchestrator to save decisions.
  - Workers do not use Engram, gentle-ai, or orchestration tooling; they only do their task and its tests.

### Left to the builder

- Exact `claude` CLI flags and Herdr commands (verify against the installed versions: `herdr --help`, `herdr agent`, `herdr pane`, `herdr worktree`).
- Whether this workflow is a skill, a script, or both.
- Pane layout (tab per wave, split grid, etc.).
- Where worker logs/results are stored for Opus to read.

### Order of work

The workflow (Part 2) is built first, since it is the means of building Part 1. It should be proven on the first real wave of Part 1 tasks.
