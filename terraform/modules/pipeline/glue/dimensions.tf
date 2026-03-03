resource "null_resource" "silver_teams_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/silver_teams.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/silver_teams.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "silver_venues_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/silver_venues.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/silver_venues.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "silver_games_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/silver_games.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/silver_games.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "silver_umpires_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/silver_umpires.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/silver_umpires.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "silver_players_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/silver_players.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/silver_players.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}
