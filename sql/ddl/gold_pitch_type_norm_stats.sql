-- gold_pitch_type_norm_stats:
-- Per-pitch-type normalization statistics (multi-season "all history") used to z-score
-- velocity and movement features for similarity calculations.
CREATE TABLE IF NOT EXISTS gold_pitch_type_norm_stats (
  pitch_type                 string,

  -- Velocity (mph)
  mu_velocity                double,
  sd_velocity                double,

  -- Movement (inches). Horizontal is glove-side normalized.
  mu_horz_break_in           double,
  sd_horz_break_in           double,
  mu_vert_break_in           double,
  sd_vert_break_in           double,

  -- Cohort size / diagnostics
  profiles_count             bigint,   -- number of (pitcher, season) profiles contributing
  sample_pitch_count         bigint,   -- sum of pitch_count contributing across those profiles

  -- Build metadata
  generated_at               timestamp
)
LOCATION 's3://{lakehouse_bucket}/gold/gold_pitch_type_norm_stats/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);