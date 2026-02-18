# Doubleday Player Catalog — Target Architecture and Design

## Goal

Expose a fast, browser-friendly catalog of MLB players by season and role so the SPA can:

- Show a list of players (pitchers now; batters later/also) for a given season (2024, 2025, 2026…).
- Provide scroll + search/autocomplete (v1: **last-name prefix**).
- Render player detail pages (e.g., pitcher graphics) keyed by **MLBAM player id**.
- Remain accurate and complete with **daily refresh** and **mid-season partial data support**.

Core constraints / preferences:

- Player IDs come from Statcast data already ingested into `silver_pitches` (Iceberg).
- Enrichment (name, position, bats/throws, current team, headshot URL) is acquired by Doubleday daily (server-side), not at request-time.
- Searching mechanics should happen primarily in the browser.
- API returns **manifest + URL** rather than serving the entire catalog via Lambda.
- Catalog can be cached; enrichment should be “**last known good**” (don’t blank fields due to temporary upstream failure).

---

## System Overview

### Key Idea

Publish a small number of **static catalog artifacts** to S3, served via CloudFront. The SPA retrieves a **manifest** via API Gateway (auth’d), then conditionally downloads the catalog blob (if changed) and performs search locally.

This avoids:
- Server-side search infrastructure (DynamoDB/OpenSearch) in v1
- Per-keystroke API calls
- Runtime dependency on MLB endpoints

### Data Products

For each season and role, publish:

- `/static/catalogs/{role}/season={YYYY}/manifest.json`
- `/static/catalogs/{role}/season={YYYY}/catalog.json`

Where:
- `role ∈ {pitchers, batters}`
- `season ∈ {2024, 2025, 2026, ...}`

---

## Data Sources

### Authoritative ID Set (from your lakehouse)

Player membership in a catalog is derived from `silver_pitches`:

- **Pitchers catalog for season Y**: distinct MLBAM ids appearing as `pitcher_id` in `silver_pitches` for season Y.
- **Batters catalog for season Y**: distinct MLBAM ids appearing as `batter_id` in `silver_pitches` for season Y.

This supports mid-season catalogs naturally: as new game_dates are ingested, the distinct ID set grows.

### Season Context Team (from your lakehouse)

Each player record includes `team_season_id`, derived from Statcast context:

- Definition: the player’s team id from their **most recent appearance in that season** (based on the last ingested pitch event for that player in that season).
- Rationale: stable “season browsing” context that will not change due to later trades.

### Current Team / Metadata (from daily enrichment)

Each player record includes `team_current_id` plus identity and traits:

- Full name (first/last)
- Primary position / role classification (for future UI filtering)
- Bats and throws
- Current team id
- Headshot URL (link to MLB-hosted image; no proxy in v1)

Enrichment is performed daily by Doubleday and written into the catalog artifacts.

---

## Daily Catalog Build Pipeline

### Trigger

- Runs daily (scheduled).
- May also run after backfills, but the daily schedule is the primary mechanism.

### Inputs

For each season to publish (initially: 2024, 2025; eventually include current season like 2026):
- `silver_pitches` Iceberg table
- MLB enrichment endpoints (server-side) for metadata

### Output

For each `(season, role)`:
- `catalog.json` (blob)
- `manifest.json` (small metadata)

### Pipeline Steps (Conceptual)

For each season S and role R:

1) **Extract ID set**
   - Pitchers: `distinct(pitcher_id)` from silver for season S.
   - Batters: `distinct(batter_id)` from silver for season S.

2) **Compute season-context team**
   - Determine `team_season_id` for each player based on “last seen” appearance in season S.

3) **Enrichment fetch**
   - For all IDs, fetch metadata (name, bats/throws, primary position, current team).
   - Construct `headshot_url` (via known MLB URL template or via metadata if provided).

4) **Last-known-good semantics**
   - If enrichment fails for a player on a given day, keep the last successful enrichment values for that player (do not overwrite with nulls).
   - If the whole enrichment job is impaired, still publish catalogs using the previous enrichment snapshot while updating membership/season team based on silver.

5) **Build teams dictionary**
   - Build a dictionary of teams referenced by any `team_season_id` or `team_current_id` in the catalog.
   - Include team `abbr` and `name` (enough for UI display; logos can be derived later if desired).

6) **Publish artifacts**
   - Write `catalog.json` and `manifest.json` to the deterministic S3 paths.
   - Prefer atomic publish patterns (write to temp key then copy/overwrite) to avoid partial reads.

---

## Artifact Contracts

### catalog.json

Top-level object with a teams dictionary plus a players array.

- `teams` keys are **strings** to avoid JSON numeric-key inconsistencies.
- `players` array holds the searchable dataset.

Example (illustrative only):

{
  "schema_version": 1,
  "season": 2026,
  "role": "pitchers",
  "teams": {
    "147": { "abbr": "NYY", "name": "Yankees" },
    "121": { "abbr": "NYM", "name": "Mets" }
  },
  "players": [
    {
      "id": 605151,
      "first": "Gerrit",
      "last": "Cole",
      "last_norm": "cole",
      "bats": "R",
      "throws": "R",
      "pos": "P",
      "team_season_id": 147,
      "team_current_id": 147,
      "headshot_url": "https://<mlb-headshot-template>/people/605151/headshot"
    }
  ]
}

Field semantics:

- `id`: MLBAM player id (integer in JSON values; used as canonical key)
- `first`, `last`: display fields
- `last_norm`: normalized last name for prefix search (lowercase, diacritics stripped, punctuation removed)
- `bats`, `throws`: single-char or short codes (e.g., L/R/S)
- `pos`: primary position code (e.g., "P", "C", "SS"); used for future role filtering
- `team_season_id`: team context from silver (season-specific)
- `team_current_id`: current team from enrichment (updates daily)
- `headshot_url`: MLB-hosted image URL (linked directly by SPA)

Notes:
- The SPA uses `team_season_id` for season browsing UI.
- The SPA may use `team_current_id` for global player pages or as fallback when `team_season_id` is missing.

### manifest.json

Small file used to:
- Tell the SPA where the blob is
- Provide cheap “has it changed?” metadata
- Provide coverage bounds to support mid-season messaging

Example (illustrative only):

{
  "schema_version": 1,
  "season": 2026,
  "role": "pitchers",
  "generated_at": "2026-05-15T03:12:44Z",
  "coverage": {
    "first_game_date_seen": "2026-03-01",
    "last_game_date_seen": "2026-05-14"
  },
  "counts": { "players": 1243, "teams": 30 },
  "catalog": {
    "url": "/static/catalogs/pitchers/season=2026/catalog.json",
    "etag": "\"abc123...\"",
    "bytes": 812345
  },
  "enrichment": {
    "as_of": "2026-05-15",
    "last_known_good": true
  }
}

Field semantics:

- `coverage.first_game_date_seen` / `coverage.last_game_date_seen`: bounds of ingested data present in silver for that season at catalog generation time
- `catalog.url`: relative path served from CloudFront
- `catalog.etag`: identifier used by SPA to decide whether to re-download the blob
- `enrichment.last_known_good`: indicates publishing retained prior enrichment values if some updates failed

---

## Serving and Access Pattern

### Why “manifest + URL”

- API Gateway returns a small auth’d response quickly.
- Catalog blob is served as a static asset via CloudFront (cheap, fast, cacheable).
- SPA performs search locally and avoids server-side search infra.

### API Endpoints

Expose manifest via API Gateway (auth’d with existing Cognito authorizer):

- GET /catalogs/pitchers?season=YYYY
- GET /catalogs/batters?season=YYYY

Response body is the manifest content (or a subset, but includes `catalog.url` and `catalog.etag`).

### CloudFront Paths

Catalog artifacts are public behind CloudFront but effectively gated by:
- returning the URL only to authenticated clients (API returns it)
- and/or CloudFront configuration if you later enforce auth at edge (optional future)

In v1, simplest is:
- catalog URLs are accessible but non-sensitive (player ids and names)
- SPA still requires auth to access the application and API

---

## Browser (SPA) Responsibilities

### Fetch + Cache Strategy

On Dashboard load (or on season/role selection):

1) Fetch manifest from API:
   - GET /catalogs/{role}?season=YYYY

2) Compare manifest `catalog.etag` to locally stored etag:
   - If same: reuse cached blob (IndexedDB/local storage/in-memory).
   - If different: download new blob from `catalog.url`.

3) Store blob + etag locally:
   - IndexedDB recommended for larger blobs and persistence.

### Search/Autocomplete

- Build an in-memory index on `last_norm` (simple array scan is fine at this scale; can optimize later).
- Prefix search:
  - normalize query to match `last_norm` rules
  - filter `players` where `player.last_norm` starts with query
  - render results, resolving team via `teams[String(team_id)]`

### Display

- For season browsing lists: display team from `team_season_id`.
- For global pages / fallback: display team from `team_current_id`.
- Show headshot by linking to `headshot_url`.

---

## Design Rationale (Trade-offs)

### Why season + role separate blobs

- Minimizes payload size and memory footprint.
- Lets the UI load only what it needs (e.g., 2024 pitchers) rather than a global mega-catalog.
- Keeps caching clear and predictable.

### Why daily enrichment for all IDs

- Dataset size is small enough that “enrich everything daily” is simpler than incremental-only logic.
- Ensures current team stays reasonably fresh.
- Combined with last-known-good semantics, avoids regressions when upstream is flaky.

### Why include both team_season_id and team_current_id

- `team_season_id` provides stable historical season context.
- `team_current_id` provides up-to-date current reality.
- Having both prevents ambiguity and avoids later schema redesign.

---

## Operational Semantics

### Mid-season partial support

- Catalog membership for season Y reflects whatever portion of season Y has been ingested so far.
- `coverage.last_game_date_seen` communicates how up-to-date the season catalog is.

### Backfills

- Backfilling older dates can introduce new players or adjust `team_season_id` (if the “last seen” changes).
- Daily rebuild naturally incorporates backfilled data.

### Failure behavior

- If enrichment fails for some players:
  - Preserve last known good enrichment values.
  - Continue publishing catalogs with updated membership derived from silver.
- If publishing fails:
  - The previous day’s artifacts remain valid and cached.

---

## Future Extensions (Explicitly Non-Goals for v1)

- Server-side search endpoints (DynamoDB/OpenSearch)
- Per-keystroke API search
- Image proxying/caching in S3
- Multi-token search, fuzzy matching, diacritics edge-case handling beyond normalization
- Cross-season merged catalog blobs

The current design keeps these open without committing to them.

---

## Summary

Doubleday will publish static, season-and-role-specific player catalog artifacts derived from the silver lakehouse and enriched daily. The API serves a small manifest that points to the CloudFront-hosted catalog blob. The browser downloads and caches the blob, performs last-name-prefix search locally, and uses both season-context and current-team fields to present stable season views alongside up-to-date enrichment.