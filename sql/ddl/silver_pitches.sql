-- statcast_pitches: canonical source-of-truth Iceberg table
-- MERGE key: (game_pk, at_bat_number, pitch_number)
CREATE TABLE IF NOT EXISTS silver_pitches (
  -- identifiers
  game_pk                                    bigint,
  at_bat_number                              int,
  pitch_number                               int,

  -- game context
  game_type                                  string,
  game_year                                  int,
  home_team                                  string,
  away_team                                  string,
  inning                                     int,
  inning_topbot                              string,
  outs_when_up                               int,
  balls                                      int,
  strikes                                    int,

  -- players
  batter                                     bigint,
  pitcher                                    bigint,
  player_name                                string,
  stand                                      string,
  p_throws                                   string,
  on_1b                                      bigint,
  on_2b                                      bigint,
  on_3b                                      bigint,
  fielder_2                                  bigint,
  fielder_3                                  bigint,
  fielder_4                                  bigint,
  fielder_5                                  bigint,
  fielder_6                                  bigint,
  fielder_7                                  bigint,
  fielder_8                                  bigint,
  fielder_9                                  bigint,

  -- pitch result
  pitch_type                                 string,
  pitch_name                                 string,
  type                                       string,
  events                                     string,
  description                                string,
  des                                        string,
  zone                                       int,
  hit_location                               int,
  bb_type                                    string,

  -- pitch tracking
  release_speed                              double,
  effective_speed                             double,
  release_spin_rate                           int,
  spin_dir                                   double,
  spin_axis                                  int,
  release_pos_x                              double,
  release_pos_y                              double,
  release_pos_z                              double,
  release_extension                          double,
  pfx_x                                      double,
  pfx_z                                      double,
  plate_x                                    double,
  plate_z                                    double,
  vx0                                        double,
  vy0                                        double,
  vz0                                        double,
  ax                                         double,
  ay                                         double,
  az                                         double,
  sz_top                                     double,
  sz_bot                                     double,
  api_break_z_with_gravity                   double,
  api_break_x_arm                            double,
  api_break_x_batter_in                      double,
  arm_angle                                  double,

  -- batted ball
  launch_speed                               double,
  launch_angle                               double,
  launch_speed_angle                         int,
  hit_distance_sc                            int,
  hc_x                                       double,
  hc_y                                       double,
  bat_speed                                  double,
  swing_length                               double,
  hyper_speed                                double,
  attack_angle                               double,
  attack_direction                           double,
  swing_path_tilt                            double,
  intercept_ball_minus_batter_pos_x_inches   double,
  intercept_ball_minus_batter_pos_y_inches   double,

  -- scoring
  home_score                                 int,
  away_score                                 int,
  bat_score                                  int,
  fld_score                                  int,
  post_home_score                            int,
  post_away_score                            int,
  post_bat_score                             int,
  post_fld_score                             int,
  home_score_diff                            int,
  bat_score_diff                             int,

  -- expected stats
  estimated_ba_using_speedangle              double,
  estimated_woba_using_speedangle            double,
  estimated_slg_using_speedangle             double,
  woba_value                                 double,
  woba_denom                                 int,
  babip_value                                double,
  iso_value                                  double,

  -- win/run expectancy
  home_win_exp                               double,
  bat_win_exp                                double,
  delta_home_win_exp                         double,
  delta_run_exp                              double,
  delta_pitcher_run_exp                      double,

  -- fielding alignment
  if_fielding_alignment                      string,
  of_fielding_alignment                      string,

  -- player metadata
  age_pit                                    int,
  age_bat                                    int,
  age_pit_legacy                             int,
  age_bat_legacy                             int,
  n_thruorder_pitcher                        int,
  n_priorpa_thisgame_player_at_bat           int,
  pitcher_days_since_prev_game               int,
  batter_days_since_prev_game                int,
  pitcher_days_until_next_game               int,
  batter_days_until_next_game                int,

  -- other
  umpire                                     bigint,
  sv_id                                      string,

  -- partition columns
  season                                     int,
  game_date                                  date
)
PARTITIONED BY (season, game_date)
LOCATION 's3://{lakehouse_bucket}/silver/silver_pitches/'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format'     = 'PARQUET'
);
