resource "null_resource" "silver_pitches_table" {
  depends_on = [aws_glue_catalog_database.main]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../sql/ddl/silver_pitches.sql")
  }

  provisioner "local-exec" {
    command     = "bash util/run_athena_query.sh sql/ddl/silver_pitches.sql ${var.project}_${var.environment} ${var.athena_results_bucket}"
    working_dir = "${path.module}/../../.."
  }
}

resource "null_resource" "silver_pitches_staging_table" {
  depends_on = [null_resource.silver_pitches_table]

  triggers = {
    sql_hash = filemd5("${path.module}/../../../sql/ddl/silver_pitches_staging.sql")
  }

  provisioner "local-exec" {
    command     = "bash util/run_athena_query.sh sql/ddl/silver_pitches_staging.sql ${var.project}_${var.environment} ${var.athena_results_bucket}"
    working_dir = "${path.module}/../../.."
  }
}
