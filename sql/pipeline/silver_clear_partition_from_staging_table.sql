DELETE FROM silver_pitches_staging
WHERE season = {season}
  AND game_date = DATE '{game_date}'
