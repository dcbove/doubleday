INSERT INTO gold_pitches_shape_season
SELECT
    pitcher,
    pitch_type,

    -- Normalized horizontal break
    avg(
        CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END
    ) AS avg_horz_break,

    avg(pfx_z) AS avg_ivb,

    stddev(
        CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END
    ) AS stddev_horz_break,

    stddev(pfx_z) AS stddev_ivb,

    approx_percentile(
        CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END, 0.1
    ) AS p10_horz_break,

    approx_percentile(
        CASE
            WHEN p_throws = 'L' THEN -pfx_x
            ELSE pfx_x
        END, 0.9
    ) AS p90_horz_break,

    approx_percentile(pfx_z, 0.1) AS p10_ivb,
    approx_percentile(pfx_z, 0.9) AS p90_ivb,

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
  AND release_speed IS NOT NULL
  AND release_extension IS NOT NULL
GROUP BY
    season,
    pitcher,
    pitch_type
HAVING count(*) >= 20
