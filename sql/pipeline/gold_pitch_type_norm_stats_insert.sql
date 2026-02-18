-- gold_pitch_type_norm_stats_insert.sql
INSERT INTO gold_pitch_type_norm_stats
SELECT
  pitch_type,

  avg(avg_velocity)                         AS mu_velocity,
  stddev_samp(avg_velocity)                 AS sd_velocity,

  avg(avg_horz_break_in)                    AS mu_horz_break_in,
  stddev_samp(avg_horz_break_in)            AS sd_horz_break_in,

  avg(avg_vert_break_in)                    AS mu_vert_break_in,
  stddev_samp(avg_vert_break_in)            AS sd_vert_break_in,

  count(*)                                  AS profiles_count,
  cast(sum(pitch_count) AS bigint)          AS sample_pitch_count,

  current_timestamp                         AS generated_at
FROM gold_pitches_shape_season
WHERE pitch_type IS NOT NULL
  AND pitch_count >= 20
GROUP BY pitch_type;