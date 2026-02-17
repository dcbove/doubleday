SELECT
    pitcher, pitch_type,
    avg_horz_break, avg_ivb, stddev_horz_break, stddev_ivb,
    p10_horz_break, p90_horz_break, p10_ivb, p90_ivb,
    avg_velocity, p10_velocity, p90_velocity, avg_adj_velocity,
    avg_spin_rate, pitch_count, usage_rate, season
FROM gold_pitches_shape_season
WHERE pitcher = {pitcher}
  AND season = {season}
