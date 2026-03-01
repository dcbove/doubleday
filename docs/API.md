# REST API

The API provides authenticated access to gold table data. It uses Cognito for authentication (with Google federation) and API Gateway with a custom Lambda authorizer.

## Domain Layout

- `doubleday-<env>.appleforge.com` — CloudFront serves the SPA and proxies `/api/*` to API Gateway. The `x-api-key` header is injected by CloudFront, so browser clients never need it.
- `api.doubleday-<env>.appleforge.com` — API Gateway directly, for non-browser clients. Requires `x-api-key` header.

## Authentication

1. **Browser**: Sign in via the SPA at `https://doubleday-<env>.appleforge.com` — Cognito OAuth flow with Google federation.

2. **CLI / non-browser**: Include the token and API key:
   ```bash
   curl -H "Authorization: Bearer <token>" \
        -H "x-api-key: <api_key>" \
        "https://api.doubleday-dev.appleforge.com/pitchers/605151/pitches?season=2024"
   ```

### Decoding a JWT

To inspect the claims in a JWT token (useful for debugging auth issues):

```bash
echo "$TOKEN" | cut -d. -f2 | tr '_-' '/+' | awk '{while(length%4)$0=$0"="}1' | base64 -d | python3 -m json.tool
```

Key claims to look for: `token_use` (`id` or `access`), `aud` (id tokens), `client_id` (access tokens), `iss`, `exp`.

## Rate Limiting

Requests require an API key (`x-api-key` header) and are subject to rate limiting (default: 50 req/s steady, 100 req/s burst). Browser requests through CloudFront have the API key injected automatically.

## Endpoints

### GET /pitchers/{pitcher_id}/pitches

Pitch-shape stats (movement, velocity, spin, usage) for a pitcher-season.

**Parameters:**
- `pitcher_id` (path, required): MLB pitcher ID (e.g., `605151`)
- `season` (query, required): Season year (e.g., `2024`)
- `pitch_type` (query, optional): Pitch type filter (e.g., `FF`, `SL`)

**Response:**
```json
{
  "pitcher": 605151,
  "season": 2024,
  "pitches": [
    {
      "pitch_type": "FF",
      "avg_velocity": 96.5,
      "p10_velocity": 94.2,
      "p90_velocity": 98.8,
      "avg_adj_velocity": 97.0,
      "avg_horz_break_in": -5.2,
      "avg_vert_break_in": 14.3,
      "stddev_horz_break_in": 1.1,
      "stddev_vert_break_in": 0.8,
      "p10_horz_break_in": -6.5,
      "p90_horz_break_in": -3.9,
      "p10_vert_break_in": 13.1,
      "p90_vert_break_in": 15.5,
      "avg_spin_rate": 2350,
      "pitch_count": 800,
      "usage_rate": 0.45
    }
  ]
}
```

### GET /pitchers/{pitcher_id}/neighbors

Shape-similarity neighbors for a pitcher-season.

**Parameters:**
- `pitcher_id` (path, required): MLB pitcher ID (e.g., `605151`)
- `season` (query, required): Season year (e.g., `2024`)

**Response:**
```json
{
  "pitcher": 605151,
  "season": 2024,
  "neighbors": [
    {
      "neighbor_pitcher": 543210,
      "neighbor_season": 2023,
      "similarity_score": 0.95,
      "rank": 1
    }
  ]
}
```

### GET /catalogs/{role}

Catalog manifest for a player role and season.

**Parameters:**
- `role` (path, required): `pitchers` or `batters`
- `season` (query, required): Season year (e.g., `2024`)

**Response (200):**
```json
{
  "manifest": {
    "season": 2024,
    "role": "pitchers",
    "blob_key": "static/catalogs/pitchers/season=2024/catalog.json",
    "etag": "abc123def456"
  }
}
```

**Response (404):** Returned when no catalog exists for the given role/season.

## OpenAPI Specification

The full OpenAPI 3.0.3 spec is available at [openapi.yaml](openapi.yaml).
