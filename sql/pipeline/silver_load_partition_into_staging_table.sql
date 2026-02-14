INSERT INTO silver_pitches_staging (
  game_pk, at_bat_number, pitch_number,
  game_type, game_year, home_team, away_team, inning, inning_topbot,
  outs_when_up, balls, strikes,
  batter, pitcher, player_name, stand, p_throws,
  on_1b, on_2b, on_3b,
  fielder_2, fielder_3, fielder_4, fielder_5, fielder_6, fielder_7, fielder_8, fielder_9,
  pitch_type, pitch_name, type, events, description, des, zone, hit_location, bb_type,
  release_speed, effective_speed, release_spin_rate, spin_dir, spin_axis,
  release_pos_x, release_pos_y, release_pos_z, release_extension,
  pfx_x, pfx_z, plate_x, plate_z,
  vx0, vy0, vz0, ax, ay, az,
  sz_top, sz_bot,
  api_break_z_with_gravity, api_break_x_arm, api_break_x_batter_in, arm_angle,
  launch_speed, launch_angle, launch_speed_angle, hit_distance_sc,
  hc_x, hc_y, bat_speed, swing_length, hyper_speed,
  attack_angle, attack_direction, swing_path_tilt,
  intercept_ball_minus_batter_pos_x_inches, intercept_ball_minus_batter_pos_y_inches,
  home_score, away_score, bat_score, fld_score,
  post_home_score, post_away_score, post_bat_score, post_fld_score,
  home_score_diff, bat_score_diff,
  estimated_ba_using_speedangle, estimated_woba_using_speedangle, estimated_slg_using_speedangle,
  woba_value, woba_denom, babip_value, iso_value,
  home_win_exp, bat_win_exp, delta_home_win_exp, delta_run_exp, delta_pitcher_run_exp,
  if_fielding_alignment, of_fielding_alignment,
  age_pit, age_bat, age_pit_legacy, age_bat_legacy,
  n_thruorder_pitcher, n_priorpa_thisgame_player_at_bat,
  pitcher_days_since_prev_game, batter_days_since_prev_game,
  pitcher_days_until_next_game, batter_days_until_next_game,
  umpire, sv_id,
  season, game_date,
  run_id,
  batch_id,
  loaded_at
)
SELECT
  -- identifiers
  try_cast(NULLIF(game_pk, '') AS bigint) AS game_pk,
  try_cast(NULLIF(at_bat_number, '') AS int) AS at_bat_number,
  try_cast(NULLIF(pitch_number, '') AS int) AS pitch_number,

  -- game context
  NULLIF(game_type, '') AS game_type,
  try_cast(NULLIF(game_year, '') AS int) AS game_year,
  NULLIF(home_team, '') AS home_team,
  NULLIF(away_team, '') AS away_team,
  try_cast(NULLIF(inning, '') AS int) AS inning,
  NULLIF(inning_topbot, '') AS inning_topbot,
  try_cast(NULLIF(outs_when_up, '') AS int) AS outs_when_up,
  try_cast(NULLIF(balls, '') AS int) AS balls,
  try_cast(NULLIF(strikes, '') AS int) AS strikes,

  -- players
  try_cast(NULLIF(batter, '') AS bigint) AS batter,
  try_cast(NULLIF(pitcher, '') AS bigint) AS pitcher,
  NULLIF(player_name, '') AS player_name,
  NULLIF(stand, '') AS stand,
  NULLIF(p_throws, '') AS p_throws,
  try_cast(NULLIF(on_1b, '') AS bigint) AS on_1b,
  try_cast(NULLIF(on_2b, '') AS bigint) AS on_2b,
  try_cast(NULLIF(on_3b, '') AS bigint) AS on_3b,
  try_cast(NULLIF(fielder_2, '') AS bigint) AS fielder_2,
  try_cast(NULLIF(fielder_3, '') AS bigint) AS fielder_3,
  try_cast(NULLIF(fielder_4, '') AS bigint) AS fielder_4,
  try_cast(NULLIF(fielder_5, '') AS bigint) AS fielder_5,
  try_cast(NULLIF(fielder_6, '') AS bigint) AS fielder_6,
  try_cast(NULLIF(fielder_7, '') AS bigint) AS fielder_7,
  try_cast(NULLIF(fielder_8, '') AS bigint) AS fielder_8,
  try_cast(NULLIF(fielder_9, '') AS bigint) AS fielder_9,

  -- pitch result
  NULLIF(pitch_type, '') AS pitch_type,
  NULLIF(pitch_name, '') AS pitch_name,
  NULLIF(type, '') AS type,
  NULLIF(events, '') AS events,
  NULLIF(description, '') AS description,
  NULLIF(des, '') AS des,
  try_cast(NULLIF(zone, '') AS int) AS zone,
  try_cast(NULLIF(hit_location, '') AS int) AS hit_location,
  NULLIF(bb_type, '') AS bb_type,

  -- pitch tracking
  try_cast(NULLIF(release_speed, '') AS double) AS release_speed,
  try_cast(NULLIF(effective_speed, '') AS double) AS effective_speed,
  try_cast(NULLIF(release_spin_rate, '') AS int) AS release_spin_rate,
  try_cast(NULLIF(spin_dir, '') AS double) AS spin_dir,
  try_cast(NULLIF(spin_axis, '') AS int) AS spin_axis,
  try_cast(NULLIF(release_pos_x, '') AS double) AS release_pos_x,
  try_cast(NULLIF(release_pos_y, '') AS double) AS release_pos_y,
  try_cast(NULLIF(release_pos_z, '') AS double) AS release_pos_z,
  try_cast(NULLIF(release_extension, '') AS double) AS release_extension,
  try_cast(NULLIF(pfx_x, '') AS double) AS pfx_x,
  try_cast(NULLIF(pfx_z, '') AS double) AS pfx_z,
  try_cast(NULLIF(plate_x, '') AS double) AS plate_x,
  try_cast(NULLIF(plate_z, '') AS double) AS plate_z,
  try_cast(NULLIF(vx0, '') AS double) AS vx0,
  try_cast(NULLIF(vy0, '') AS double) AS vy0,
  try_cast(NULLIF(vz0, '') AS double) AS vz0,
  try_cast(NULLIF(ax, '') AS double) AS ax,
  try_cast(NULLIF(ay, '') AS double) AS ay,
  try_cast(NULLIF(az, '') AS double) AS az,
  try_cast(NULLIF(sz_top, '') AS double) AS sz_top,
  try_cast(NULLIF(sz_bot, '') AS double) AS sz_bot,
  try_cast(NULLIF(api_break_z_with_gravity, '') AS double) AS api_break_z_with_gravity,
  try_cast(NULLIF(api_break_x_arm, '') AS double) AS api_break_x_arm,
  try_cast(NULLIF(api_break_x_batter_in, '') AS double) AS api_break_x_batter_in,
  try_cast(NULLIF(arm_angle, '') AS double) AS arm_angle,

  -- batted ball
  try_cast(NULLIF(launch_speed, '') AS double) AS launch_speed,
  try_cast(NULLIF(launch_angle, '') AS double) AS launch_angle,
  try_cast(NULLIF(launch_speed_angle, '') AS int) AS launch_speed_angle,
  try_cast(NULLIF(hit_distance_sc, '') AS int) AS hit_distance_sc,
  try_cast(NULLIF(hc_x, '') AS double) AS hc_x,
  try_cast(NULLIF(hc_y, '') AS double) AS hc_y,
  try_cast(NULLIF(bat_speed, '') AS double) AS bat_speed,
  try_cast(NULLIF(swing_length, '') AS double) AS swing_length,
  try_cast(NULLIF(hyper_speed, '') AS double) AS hyper_speed,
  try_cast(NULLIF(attack_angle, '') AS double) AS attack_angle,
  try_cast(NULLIF(attack_direction, '') AS double) AS attack_direction,
  try_cast(NULLIF(swing_path_tilt, '') AS double) AS swing_path_tilt,
  try_cast(NULLIF(intercept_ball_minus_batter_pos_x_inches, '') AS double) AS intercept_ball_minus_batter_pos_x_inches,
  try_cast(NULLIF(intercept_ball_minus_batter_pos_y_inches, '') AS double) AS intercept_ball_minus_batter_pos_y_inches,

  -- scoring
  try_cast(NULLIF(home_score, '') AS int) AS home_score,
  try_cast(NULLIF(away_score, '') AS int) AS away_score,
  try_cast(NULLIF(bat_score, '') AS int) AS bat_score,
  try_cast(NULLIF(fld_score, '') AS int) AS fld_score,
  try_cast(NULLIF(post_home_score, '') AS int) AS post_home_score,
  try_cast(NULLIF(post_away_score, '') AS int) AS post_away_score,
  try_cast(NULLIF(post_bat_score, '') AS int) AS post_bat_score,
  try_cast(NULLIF(post_fld_score, '') AS int) AS post_fld_score,
  try_cast(NULLIF(home_score_diff, '') AS int) AS home_score_diff,
  try_cast(NULLIF(bat_score_diff, '') AS int) AS bat_score_diff,

  -- expected stats
  try_cast(NULLIF(estimated_ba_using_speedangle, '') AS double) AS estimated_ba_using_speedangle,
  try_cast(NULLIF(estimated_woba_using_speedangle, '') AS double) AS estimated_woba_using_speedangle,
  try_cast(NULLIF(estimated_slg_using_speedangle, '') AS double) AS estimated_slg_using_speedangle,
  try_cast(NULLIF(woba_value, '') AS double) AS woba_value,
  try_cast(NULLIF(woba_denom, '') AS int) AS woba_denom,
  try_cast(NULLIF(babip_value, '') AS double) AS babip_value,
  try_cast(NULLIF(iso_value, '') AS double) AS iso_value,

  -- win/run expectancy
  try_cast(NULLIF(home_win_exp, '') AS double) AS home_win_exp,
  try_cast(NULLIF(bat_win_exp, '') AS double) AS bat_win_exp,
  try_cast(NULLIF(delta_home_win_exp, '') AS double) AS delta_home_win_exp,
  try_cast(NULLIF(delta_run_exp, '') AS double) AS delta_run_exp,
  try_cast(NULLIF(delta_pitcher_run_exp, '') AS double) AS delta_pitcher_run_exp,

  -- fielding alignment
  NULLIF(if_fielding_alignment, '') AS if_fielding_alignment,
  NULLIF(of_fielding_alignment, '') AS of_fielding_alignment,

  -- player metadata
  try_cast(NULLIF(age_pit, '') AS int) AS age_pit,
  try_cast(NULLIF(age_bat, '') AS int) AS age_bat,
  try_cast(NULLIF(age_pit_legacy, '') AS int) AS age_pit_legacy,
  try_cast(NULLIF(age_bat_legacy, '') AS int) AS age_bat_legacy,
  try_cast(NULLIF(n_thruorder_pitcher, '') AS int) AS n_thruorder_pitcher,
  try_cast(NULLIF(n_priorpa_thisgame_player_at_bat, '') AS int) AS n_priorpa_thisgame_player_at_bat,
  try_cast(NULLIF(pitcher_days_since_prev_game, '') AS int) AS pitcher_days_since_prev_game,
  try_cast(NULLIF(batter_days_since_prev_game, '') AS int) AS batter_days_since_prev_game,
  try_cast(NULLIF(pitcher_days_until_next_game, '') AS int) AS pitcher_days_until_next_game,
  try_cast(NULLIF(batter_days_until_next_game, '') AS int) AS batter_days_until_next_game,

  -- other
  try_cast(NULLIF(umpire, '') AS bigint) AS umpire,
  NULLIF(sv_id, '') AS sv_id,

  -- partition columns
  season,
  game_date,

  -- per-run isolation
  '{run_id}' AS run_id,
  '{batch_id}' AS batch_id,
  CURRENT_TIMESTAMP AS loaded_at

FROM bronze_statcast
WHERE season = {season}
  AND game_date = DATE '{game_date}'
  AND try_cast(NULLIF(game_pk, '') AS bigint) IS NOT NULL
  AND try_cast(NULLIF(at_bat_number, '') AS int) IS NOT NULL
  AND try_cast(NULLIF(pitch_number, '') AS int) IS NOT NULL