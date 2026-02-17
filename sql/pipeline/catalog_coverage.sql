SELECT CAST(MIN(game_date) AS VARCHAR) AS first_game_date,
       CAST(MAX(game_date) AS VARCHAR) AS last_game_date
FROM silver_pitches WHERE season = {season}
