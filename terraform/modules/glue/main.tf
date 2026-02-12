resource "aws_glue_catalog_database" "main" {
  name = "${var.project}_${var.environment}"
}

resource "aws_glue_catalog_table" "bronze_statcast" {
  database_name = aws_glue_catalog_database.main.name
  name          = "bronze_statcast"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "classification"         = "csv"
    "skip.header.line.count" = "1"
    "EXTERNAL"               = "TRUE"

    "projection.enabled"            = "true"
    "projection.season.type"        = "integer"
    "projection.season.range"       = "2024,2025"
    "projection.game_date.type"     = "date"
    "projection.game_date.format"   = "yyyy-MM-dd"
    "projection.game_date.range"    = "2024-03-01,NOW"
    "projection.game_date.interval" = "1"
    "projection.game_date.interval.unit" = "DAYS"

    "storage.location.template" = "s3://${var.lakehouse_bucket_name}/bronze/season=$${season}/game_date=$${game_date}"
  }

  storage_descriptor {
    location      = "s3://${var.lakehouse_bucket_name}/bronze/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.OpenCSVSerde"
      parameters = {
        "separatorChar" = ","
        "quoteChar"     = "\""
      }
    }

    columns {
      name = "pitch_type"
      type = "string"
    }
    columns {
      name = "csv_game_date"
      type = "string"
    }
    columns {
      name = "release_speed"
      type = "string"
    }
    columns {
      name = "release_pos_x"
      type = "string"
    }
    columns {
      name = "release_pos_z"
      type = "string"
    }
    columns {
      name = "player_name"
      type = "string"
    }
    columns {
      name = "batter"
      type = "string"
    }
    columns {
      name = "pitcher"
      type = "string"
    }
    columns {
      name = "events"
      type = "string"
    }
    columns {
      name = "description"
      type = "string"
    }
    columns {
      name = "spin_dir"
      type = "string"
    }
    columns {
      name = "spin_rate_deprecated"
      type = "string"
    }
    columns {
      name = "break_angle_deprecated"
      type = "string"
    }
    columns {
      name = "break_length_deprecated"
      type = "string"
    }
    columns {
      name = "zone"
      type = "string"
    }
    columns {
      name = "des"
      type = "string"
    }
    columns {
      name = "game_type"
      type = "string"
    }
    columns {
      name = "stand"
      type = "string"
    }
    columns {
      name = "p_throws"
      type = "string"
    }
    columns {
      name = "home_team"
      type = "string"
    }
    columns {
      name = "away_team"
      type = "string"
    }
    columns {
      name = "type"
      type = "string"
    }
    columns {
      name = "hit_location"
      type = "string"
    }
    columns {
      name = "bb_type"
      type = "string"
    }
    columns {
      name = "balls"
      type = "string"
    }
    columns {
      name = "strikes"
      type = "string"
    }
    columns {
      name = "game_year"
      type = "string"
    }
    columns {
      name = "pfx_x"
      type = "string"
    }
    columns {
      name = "pfx_z"
      type = "string"
    }
    columns {
      name = "plate_x"
      type = "string"
    }
    columns {
      name = "plate_z"
      type = "string"
    }
    columns {
      name = "on_3b"
      type = "string"
    }
    columns {
      name = "on_2b"
      type = "string"
    }
    columns {
      name = "on_1b"
      type = "string"
    }
    columns {
      name = "outs_when_up"
      type = "string"
    }
    columns {
      name = "inning"
      type = "string"
    }
    columns {
      name = "inning_topbot"
      type = "string"
    }
    columns {
      name = "hc_x"
      type = "string"
    }
    columns {
      name = "hc_y"
      type = "string"
    }
    columns {
      name = "tfs_deprecated"
      type = "string"
    }
    columns {
      name = "tfs_zulu_deprecated"
      type = "string"
    }
    columns {
      name = "umpire"
      type = "string"
    }
    columns {
      name = "sv_id"
      type = "string"
    }
    columns {
      name = "vx0"
      type = "string"
    }
    columns {
      name = "vy0"
      type = "string"
    }
    columns {
      name = "vz0"
      type = "string"
    }
    columns {
      name = "ax"
      type = "string"
    }
    columns {
      name = "ay"
      type = "string"
    }
    columns {
      name = "az"
      type = "string"
    }
    columns {
      name = "sz_top"
      type = "string"
    }
    columns {
      name = "sz_bot"
      type = "string"
    }
    columns {
      name = "hit_distance_sc"
      type = "string"
    }
    columns {
      name = "launch_speed"
      type = "string"
    }
    columns {
      name = "launch_angle"
      type = "string"
    }
    columns {
      name = "effective_speed"
      type = "string"
    }
    columns {
      name = "release_spin_rate"
      type = "string"
    }
    columns {
      name = "release_extension"
      type = "string"
    }
    columns {
      name = "game_pk"
      type = "string"
    }
    columns {
      name = "fielder_2"
      type = "string"
    }
    columns {
      name = "fielder_3"
      type = "string"
    }
    columns {
      name = "fielder_4"
      type = "string"
    }
    columns {
      name = "fielder_5"
      type = "string"
    }
    columns {
      name = "fielder_6"
      type = "string"
    }
    columns {
      name = "fielder_7"
      type = "string"
    }
    columns {
      name = "fielder_8"
      type = "string"
    }
    columns {
      name = "fielder_9"
      type = "string"
    }
    columns {
      name = "release_pos_y"
      type = "string"
    }
    columns {
      name = "estimated_ba_using_speedangle"
      type = "string"
    }
    columns {
      name = "estimated_woba_using_speedangle"
      type = "string"
    }
    columns {
      name = "woba_value"
      type = "string"
    }
    columns {
      name = "woba_denom"
      type = "string"
    }
    columns {
      name = "babip_value"
      type = "string"
    }
    columns {
      name = "iso_value"
      type = "string"
    }
    columns {
      name = "launch_speed_angle"
      type = "string"
    }
    columns {
      name = "at_bat_number"
      type = "string"
    }
    columns {
      name = "pitch_number"
      type = "string"
    }
    columns {
      name = "pitch_name"
      type = "string"
    }
    columns {
      name = "home_score"
      type = "string"
    }
    columns {
      name = "away_score"
      type = "string"
    }
    columns {
      name = "bat_score"
      type = "string"
    }
    columns {
      name = "fld_score"
      type = "string"
    }
    columns {
      name = "post_away_score"
      type = "string"
    }
    columns {
      name = "post_home_score"
      type = "string"
    }
    columns {
      name = "post_bat_score"
      type = "string"
    }
    columns {
      name = "post_fld_score"
      type = "string"
    }
    columns {
      name = "if_fielding_alignment"
      type = "string"
    }
    columns {
      name = "of_fielding_alignment"
      type = "string"
    }
    columns {
      name = "spin_axis"
      type = "string"
    }
    columns {
      name = "delta_home_win_exp"
      type = "string"
    }
    columns {
      name = "delta_run_exp"
      type = "string"
    }
    columns {
      name = "bat_speed"
      type = "string"
    }
    columns {
      name = "swing_length"
      type = "string"
    }
    columns {
      name = "estimated_slg_using_speedangle"
      type = "string"
    }
    columns {
      name = "delta_pitcher_run_exp"
      type = "string"
    }
    columns {
      name = "hyper_speed"
      type = "string"
    }
    columns {
      name = "home_score_diff"
      type = "string"
    }
    columns {
      name = "bat_score_diff"
      type = "string"
    }
    columns {
      name = "home_win_exp"
      type = "string"
    }
    columns {
      name = "bat_win_exp"
      type = "string"
    }
    columns {
      name = "age_pit_legacy"
      type = "string"
    }
    columns {
      name = "age_bat_legacy"
      type = "string"
    }
    columns {
      name = "age_pit"
      type = "string"
    }
    columns {
      name = "age_bat"
      type = "string"
    }
    columns {
      name = "n_thruorder_pitcher"
      type = "string"
    }
    columns {
      name = "n_priorpa_thisgame_player_at_bat"
      type = "string"
    }
    columns {
      name = "pitcher_days_since_prev_game"
      type = "string"
    }
    columns {
      name = "batter_days_since_prev_game"
      type = "string"
    }
    columns {
      name = "pitcher_days_until_next_game"
      type = "string"
    }
    columns {
      name = "batter_days_until_next_game"
      type = "string"
    }
    columns {
      name = "api_break_z_with_gravity"
      type = "string"
    }
    columns {
      name = "api_break_x_arm"
      type = "string"
    }
    columns {
      name = "api_break_x_batter_in"
      type = "string"
    }
    columns {
      name = "arm_angle"
      type = "string"
    }
    columns {
      name = "attack_angle"
      type = "string"
    }
    columns {
      name = "attack_direction"
      type = "string"
    }
    columns {
      name = "swing_path_tilt"
      type = "string"
    }
    columns {
      name = "intercept_ball_minus_batter_pos_x_inches"
      type = "string"
    }
    columns {
      name = "intercept_ball_minus_batter_pos_y_inches"
      type = "string"
    }
  }

  partition_keys {
    name = "season"
    type = "int"
  }
  partition_keys {
    name = "game_date"
    type = "date"
  }
}
