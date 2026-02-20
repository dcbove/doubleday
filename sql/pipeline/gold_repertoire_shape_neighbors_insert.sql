-- gold_repertoire_shape_neighbors_insert.sql

INSERT INTO gold_repertoire_shape_neighbors
WITH
profile_totals AS (
  SELECT
    pitcher,
    season,
    cast(sum(pitch_count) AS bigint) AS total_pitch_count,
    count(*) AS pitch_types_count
  FROM gold_pitches_shape_season
  GROUP BY pitcher, season
),

eligible_profiles AS (
  SELECT pitcher, season, total_pitch_count, pitch_types_count
  FROM profile_totals
  WHERE total_pitch_count >= 250
),

profile_pitch_features AS (
  SELECT
    g.pitcher,
    g.season,
    g.pitch_type,
    (g.avg_velocity      - n.mu_velocity)       / nullif(n.sd_velocity, 0)       AS z_vel,
    (g.avg_horz_break_in - n.mu_horz_break_in)  / nullif(n.sd_horz_break_in, 0)  AS z_horz,
    (g.avg_vert_break_in - n.mu_vert_break_in)  / nullif(n.sd_vert_break_in, 0)  AS z_vert
  FROM gold_pitches_shape_season g
  JOIN gold_pitch_type_norm_stats n
    ON g.pitch_type = n.pitch_type
  JOIN eligible_profiles e
    ON g.pitcher = e.pitcher AND g.season = e.season
  WHERE g.pitch_count >= 20
),

pairs AS (
  SELECT
    a.pitcher AS source_pitcher,
    a.season  AS source_season,
    b.pitcher AS neighbor_pitcher,
    b.season  AS neighbor_season
  FROM eligible_profiles a
  JOIN eligible_profiles b
    ON NOT (a.pitcher = b.pitcher AND a.season = b.season)
),

shared_pitch_dists AS (
  SELECT
    p.source_pitcher,
    p.source_season,
    p.neighbor_pitcher,
    p.neighbor_season,

    count(*) AS shared_pitch_types_count,  -- BIGINT

    avg(
      sqrt(
        pow(a.z_vel  - b.z_vel,  2) +
        pow(a.z_horz - b.z_horz, 2) +
        pow(a.z_vert - b.z_vert, 2)
      )
    ) AS distance_shape
  FROM pairs p
  JOIN profile_pitch_features a
    ON a.pitcher = p.source_pitcher
   AND a.season  = p.source_season
  JOIN profile_pitch_features b
    ON b.pitcher = p.neighbor_pitcher
   AND b.season  = p.neighbor_season
   AND b.pitch_type = a.pitch_type
  GROUP BY
    p.source_pitcher, p.source_season,
    p.neighbor_pitcher, p.neighbor_season
),

arsenal_sizes AS (
  SELECT
    p.source_pitcher,
    p.source_season,
    p.neighbor_pitcher,
    p.neighbor_season,
    es.pitch_types_count AS source_pitch_types_count,   -- BIGINT
    en.pitch_types_count AS neighbor_pitch_types_count  -- BIGINT
  FROM pairs p
  JOIN eligible_profiles es
    ON es.pitcher = p.source_pitcher AND es.season = p.source_season
  JOIN eligible_profiles en
    ON en.pitcher = p.neighbor_pitcher AND en.season = p.neighbor_season
),

scored AS (
  SELECT
    d.source_pitcher,
    d.source_season,
    d.neighbor_pitcher,
    d.neighbor_season,

    d.shared_pitch_types_count,
    s.source_pitch_types_count,
    s.neighbor_pitch_types_count,

    (s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count)
      AS union_pitch_types_count,

    ((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count)
      - d.shared_pitch_types_count) AS arsenal_mismatch_count,

    d.distance_shape,

    ({lambda} * (
      cast(
        ((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count)
          - d.shared_pitch_types_count) AS double
      )
      /
      nullif(
        cast((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count) AS double),
        0.0
      )
    )) AS arsenal_penalty,

    d.distance_shape
    +
    ({lambda} * (
      cast(
        ((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count)
          - d.shared_pitch_types_count) AS double
      )
      /
      nullif(
        cast((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count) AS double),
        0.0
      )
    )) AS distance_total,

    exp(
      -(
        d.distance_shape
        +
        ({lambda} * (
          cast(
            ((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count)
              - d.shared_pitch_types_count) AS double
          )
          /
          nullif(
            cast((s.source_pitch_types_count + s.neighbor_pitch_types_count - d.shared_pitch_types_count) AS double),
            0.0
          )
        ))
      ) / {tau}
    ) AS similarity_score,

    current_timestamp AS generated_at
  FROM shared_pitch_dists d
  JOIN arsenal_sizes s
    ON s.source_pitcher = d.source_pitcher
   AND s.source_season  = d.source_season
   AND s.neighbor_pitcher = d.neighbor_pitcher
   AND s.neighbor_season  = d.neighbor_season
  WHERE d.shared_pitch_types_count >= 1
),

ranked AS (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY source_pitcher, source_season
      ORDER BY distance_total ASC
    ) AS rank_bigint
  FROM scored
)

SELECT
  source_pitcher,
  source_season,
  neighbor_pitcher,
  neighbor_season,
  similarity_score,

  cast(rank_bigint AS integer) AS rank,

  distance_total,
  distance_shape,

  cast(shared_pitch_types_count AS integer)   AS shared_pitch_types_count,
  cast(source_pitch_types_count AS integer)   AS source_pitch_types_count,
  cast(neighbor_pitch_types_count AS integer) AS neighbor_pitch_types_count,
  cast(arsenal_mismatch_count AS integer)     AS arsenal_mismatch_count,

  arsenal_penalty,
  generated_at
FROM ranked
WHERE rank_bigint <= 20;
