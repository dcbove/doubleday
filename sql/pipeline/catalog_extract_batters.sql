WITH ranked AS (
    SELECT
        batter AS player_id,
        CASE WHEN inning_topbot = 'Top' THEN away_team ELSE home_team END AS team_abbr,
        ROW_NUMBER() OVER (
            PARTITION BY batter
            ORDER BY game_date DESC, game_pk DESC, at_bat_number DESC, pitch_number DESC
        ) AS rn
    FROM silver_pitches
    WHERE season = {season}
)
SELECT player_id, team_abbr FROM ranked WHERE rn = 1 ORDER BY player_id
