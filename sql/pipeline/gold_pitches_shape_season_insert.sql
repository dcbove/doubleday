INSERT INTO gold_pitches_shape_season
SELECT
    pitcher,
    pitch_type,

    -- Movement (inches). Horizontal is normalized so "glove-side" is positive.
    avg(
        12.0 * CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END
    ) AS avg_horz_break_in,

    avg(12.0 * pfx_z) AS avg_vert_break_in,

    stddev(
        12.0 * CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END
    ) AS stddev_horz_break_in,

    stddev(12.0 * pfx_z) AS stddev_vert_break_in,

    approx_percentile(
        12.0 * CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END, 0.1
    ) AS p10_horz_break_in,

    approx_percentile(
        12.0 * CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END, 0.9
    ) AS p90_horz_break_in,

    approx_percentile(12.0 * pfx_z, 0.1) AS p10_vert_break_in,
    approx_percentile(12.0 * pfx_z, 0.9) AS p90_vert_break_in,

    -- Velocity
    avg(release_speed) AS avg_velocity,
    approx_percentile(release_speed, 0.1) AS p10_velocity,
    approx_percentile(release_speed, 0.9) AS p90_velocity,

    -- Extension-adjusted velocity
    avg(
        release_speed * (60.5 / (60.5 - release_extension))
    ) AS avg_adj_velocity,

    -- Spin
    avg(release_spin_rate) AS avg_spin_rate,

    count(*) AS pitch_count,

    CAST(count(*) AS double) / sum(count(*)) OVER (PARTITION BY season, pitcher) AS usage_rate,

    -- Partition column last (matches table definition order)
    season

FROM silver_pitches
WHERE season = {season}
  AND game_type = 'R'
  AND pfx_x IS NOT NULL
  AND pfx_z IS NOT NULL
  AND p_throws IS NOT NULL
  AND release_speed IS NOT NULL
  AND release_extension IS NOT NULL
GROUP BY
    season,
    pitcher,
    pitch_type
HAVING count(*) >= 20;