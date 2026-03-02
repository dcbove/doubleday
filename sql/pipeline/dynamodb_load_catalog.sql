SELECT
    player_id, first_name, last_name, last_norm,
    bats, throws, position,
    team_season_id, team_season_abbr, team_season_name,
    team_current_id, team_current_abbr, team_current_name,
    headshot_url, role, season
FROM gold_catalog
WHERE season = {season}
