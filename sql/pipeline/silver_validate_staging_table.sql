SELECT COUNT(*) AS duplicate_keys
FROM (
    SELECT game_pk, at_bat_number, pitch_number
    FROM silver_pitches_staging
    WHERE season = {season} AND game_date = DATE '{game_date}'
    GROUP BY game_pk, at_bat_number, pitch_number
    HAVING COUNT(*) > 1
)
