resource "null_resource" "gold_pitches_shape_season_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../sql/ddl/gold_pitches_shape_season.sql")
  }

  provisioner "local-exec" {
    command     = "bash util/run_athena_query.sh sql/ddl/gold_pitches_shape_season.sql ${var.project}_${var.environment} ${var.athena_results_bucket}"
    working_dir = "${path.module}/../../.."
  }
}
