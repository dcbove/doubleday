-- gold_repertoire_shape_neighbors:
-- Top-N cross-season repertoire shape similarity neighbors per pitcher-season profile

CREATE TABLE IF NOT EXISTS gold_repertoire_shape_neighbors (
  source_pitcher              bigint,
  source_season               int,

  neighbor_pitcher            bigint,
  neighbor_season             int,

  similarity_score            double,
  rank                        int,

  -- Distance decomposition (useful for debugging / UI transparency)
  distance_total              double,
  distance_shape              double,

  -- Arsenal structure diagnostics
  shared_pitch_types_count    int,
  source_pitch_types_count    int,
  neighbor_pitch_types_count  int,
  arsenal_mismatch_count      int,
  arsenal_penalty             double,

  -- Build metadata
  generated_at                timestamp
)
PARTITIONED BY (source_season)
LOCATION 's3://{lakehouse_bucket}/gold/gold_repertoire_shape_neighbors/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);