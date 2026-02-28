SELECT
    pitcher, pitch_type,
    avg_horz_break_in, avg_vert_break_in,
    stddev_horz_break_in, stddev_vert_break_in,
    p10_horz_break_in, p90_horz_break_in,
    p10_vert_break_in, p90_vert_break_in,
    avg_velocity, p10_velocity, p90_velocity, avg_adj_velocity,
    avg_spin_rate, pitch_count, usage_rate, season
FROM gold_pitches_shape_season
WHERE season = {season}
