# PROJECT_STATUS.md

## Project Metadata
- **Project**: YouTube Video Performance Determinants in French Popular Science
- **Language**: French (`fr`)
- **Niche**: Science & Educational Popularization ("Vulgarisation scientifique et culturelle")
- **Period**: `2024-01-01T00:00:00Z` to `2025-12-31T23:59:59Z` (24-month historical cohort)
- **Timezone**: `Europe/Paris` (UTC+1 / UTC+2 DST)
- **Shorts Policy**: Strictly excluded from primary hypothesis testing (duration > 60s); Shorts used for robustness leakage testing.
- **Primary Metric**: Relative performance (`views / median(views)_channel`) + ln(views) with channel fixed effects.

---

## Phase Checklist
- [x] **Phase 0: Scoping & Hypotheses**
  - [x] Niche boundary defined
  - [x] Period locked
  - [x] Hypotheses pre-registered
- [x] **Phase 1: Technical Setup**
  - [x] Google Cloud YouTube Data API v3 key provisioned & tested
  - [x] Neon PostgreSQL database provisioned & connection verified
  - [x] Python virtual environment & dependency management
  - [x] `.env` & configuration parsing
- [x] **Phase 2: PostgreSQL Relational Schema**
  - [x] DDL for `chaines`, `videos`, `statistiques`, `chaines_stats`, `raw_api`
  - [x] Constraints, keys, and indexes
- [x] **Phase 3: Stratified Channel Selection**
  - [x] 60-100 channels identified across 3 strata (<50k, 50k-500k, >500k)
  - [x] Justification and documentation of sampling (64 verified channels: 18 in `<50k`, 25 in `50k-500k`, 21 in `>500k`)
- [x] **Phase 4: API Extraction Pipeline**
  - [x] Quota estimation & management (~180 quota units consumed out of 10,000 daily limit)
  - [x] Exponential backoff / retry handling implemented via decorator
  - [x] Raw JSON persistence in `raw_api` (3,346 payloads archived)
- [x] **Phase 5: Idempotent Ingestion & Data Quality**
  - [x] ON CONFLICT staging / upsert logic
  - [x] Integrity checks (0 corrupted rows, 2,138 long-form videos > 60s, 1,208 Shorts tagged)
- [x] **Phase 6: SQL Feature Engineering**
  - [x] View `features` with regex extraction, CTE median, and relative performance (2,130 observations ready)
- [x] **Phase 7: Statistical Analysis in Python**
  - [x] EDA & distribution checks (log-normal views, skewness 10.14 -> -0.83 on log scale)
  - [x] Non-parametric tests (Mann-Whitney U, Cliff's delta)
  - [x] Multiple testing correction (Benjamini-Hochberg FDR)
  - [x] OLS regression with channel fixed effects and clustered standard errors (R² = 0.775)
- [x] **Phase 8: Robustness Checks & Limitations**
  - [x] Shorts leakage test: demonstrated that mixing Shorts artificially distorts duration p-value to p=0.047 and dilutes number signal.
  - [x] Stratum heterogeneity: discovered that title optimizations (numbers +47%, negative words +47%) drive performance on large channels (>500k) but have zero to negligible leverage on smaller creators (<500k).
  - [x] Limitations documented (observational vs causal, no CTR/retention, regex sentiment simplicity, survivorship bias).
- [x] **Phase 9: Deliverables (Notebook, Charts, README, LinkedIn Post)**
  - [x] 4 publication-quality charts saved in `assets/` (300 DPI)
  - [x] Reproducible Jupyter Notebook with visible outputs (`notebooks/analysis.ipynb`)
  - [x] Comprehensive production-grade `README.md` with Mermaid ER diagram and reproduction guide
  - [x] Honest, non-clickbait LinkedIn post

---

## Pre-Registered Hypotheses Status
| Hypothesis | Feature | Operationalization | Direction (H1) | Empirical Result (OLS FE) | Status |
|---|---|---|---|---|---|
| **H1** | Duration | Video duration in minutes | Positive up to plateau | $\beta = +0.0022, p=0.2300$ (+0.2%/min) | **RÉFUTÉE** |
| **H2** | Numbers in Title | `title ~ '[0-9]'` | Positive | $\beta = +0.2385, p=0.0450$ (+26.9%) | **CONFIRMÉE** |
| **H3** | Question in Title | `title ~ '\?'` or interrogative prefix | Positive | $\beta = -0.0262, p=0.7048$ (-2.6%) | **RÉFUTÉE** |
| **H4** | Negativity Bias | Lexicon check (`erreur`, `pire`, `faux`, etc.) | Positive | $\beta = +0.3363, p<0.0001$ (+40.0%) | **CONFIRMÉE** |
| **H5** | Prime Publishing Time | Wed/Sun 17:00-20:59 CET | Positive | $\beta = +0.2223, p=0.0703$ (+24.9%) | **NON CONCLUANTE** |
| **H6** | Title Length | Character count (optimal range 40-70 chars) | Inverted-U | $\beta = +0.0041, p=0.1760$ (+0.4%/char) | **RÉFUTÉE** |

---

## Log of Key Decisions
- **2026-10-21**: Rejected broad 'entertainment' and unobservable 'high budget' niches in favor of French Science & Popularization to guarantee cross-stratum sample validity (<50k to >500k).
- **2026-10-21**: Locked 2024-2025 cohort to ensure 100% mature video metrics (>30 days old).
- **2026-10-22**: Validated relational schema with BIGINT counters, TIMESTAMPTZ, and indexes on Neon PostgreSQL.
- **2026-10-24**: Stratified sample finalized with 64 verified active French popular science creators using peer snowball sampling (18 in `<50k`, 25 in `50k-500k`, 21 in `>500k`).
- **2026-10-25**: Completed extraction pipeline: 3,346 total videos extracted (2,138 long-form >60s, 1,208 Shorts) with 0 data quality errors.
- **2026-10-25**: Deployed `features` view with CTE median, POSIX regex `\y` word boundaries, and Europe/Paris timezone extraction. 2,130 mature observations.
- **2026-11-05**: Completed Phase 7 econometric analysis: H2 and H4 confirmed (+26.9% for numbers, +40.0% for negative lexemes). H1, H3, H6 refuted. H5 inconclusive. R² = 0.775 with channel fixed effects and clustered standard errors.
- **2026-11-05**: Robustness checks completed: demonstrated distortion from Shorts leakage and discovered severe stratum heterogeneity (packaging effects are concentrated on >500k channels).
- **2026-11-05**: All final deliverables completed: 4 high-res charts in `assets/`, executed `notebooks/analysis.ipynb`, production `README.md`, and LinkedIn publication draft.
