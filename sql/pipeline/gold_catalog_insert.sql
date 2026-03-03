INSERT INTO gold_catalog
WITH pitchers AS (
    SELECT
        pitcher AS player_id,
        CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END AS team_abbr,
        ROW_NUMBER() OVER (
            PARTITION BY pitcher
            ORDER BY game_date DESC, game_pk DESC, at_bat_number DESC, pitch_number DESC
        ) AS rn
    FROM silver_pitches
    WHERE season = {season}
),
batters AS (
    SELECT
        batter AS player_id,
        CASE WHEN inning_topbot = 'Top' THEN away_team ELSE home_team END AS team_abbr,
        ROW_NUMBER() OVER (
            PARTITION BY batter
            ORDER BY game_date DESC, game_pk DESC, at_bat_number DESC, pitch_number DESC
        ) AS rn
    FROM silver_pitches
    WHERE season = {season}
),
combined AS (
    SELECT player_id, team_abbr, 'pitcher' AS role FROM pitchers WHERE rn = 1
    UNION ALL
    SELECT player_id, team_abbr, 'batter' AS role FROM batters WHERE rn = 1
)
SELECT
    c.player_id,
    p.first_name,
    p.last_name,
    p.last_norm,
    p.bats,
    p.throws,
    p.position,
    st.team_id     AS team_season_id,
    st.abbreviation AS team_season_abbr,
    st.full_name   AS team_season_name,
    ct.team_id     AS team_current_id,
    ct.abbreviation AS team_current_abbr,
    ct.full_name   AS team_current_name,
    p.headshot_url,
    c.role,
    {season}       AS season
FROM combined c
JOIN silver_players p
    ON c.player_id = p.player_id AND p.season = {season}
LEFT JOIN silver_teams st
    ON c.team_abbr = st.abbreviation AND st.season = {season}
LEFT JOIN silver_teams ct
    ON p.current_team_id = ct.team_id AND ct.season = {season}
