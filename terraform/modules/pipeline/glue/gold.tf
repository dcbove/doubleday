resource "null_resource" "gold_pitches_shape_season_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/gold_pitches_shape_season.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/gold_pitches_shape_season.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "gold_pitch_type_norm_stats_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/gold_pitch_type_norm_stats.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/gold_pitch_type_norm_stats.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "gold_repertoire_shape_neighbors_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/gold_repertoire_shape_neighbors.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/gold_repertoire_shape_neighbors.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}

resource "null_resource" "gold_catalog_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../../sql/ddl/gold_catalog.sql")
  }

  provisioner "local-exec" {
    command     = "bash scripts/run_athena_query.sh sql/ddl/gold_catalog.sql ${var.project}_${var.environment} ${var.athena_results_bucket} ${var.lakehouse_bucket_name}"
    working_dir = "${path.module}/../../../.."
  }
}
