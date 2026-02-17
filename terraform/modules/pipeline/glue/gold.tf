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
