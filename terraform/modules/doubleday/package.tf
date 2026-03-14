locals {
  project_root = "${path.module}/../../.."
  lambda_dir   = "${local.project_root}/builds/lambdas"

  # Per-Lambda zips built by Bazel (bazel build //src/doubleday/... + copy_lambda_zips.sh).
  lambda_packages = {
    for name in [
      "validate_input", "check_failures", "bronze_load", "silver_load",
      "clear_staging", "gold_load", "dynamodb_load", "dimension_load",
      "daily_trigger", "authorizer", "catalog", "query_pitches",
      "query_neighbors", "create_checkout", "customer_portal",
      "stripe_events", "subscription_status",
    ] : name => {
      path = "${local.lambda_dir}/${name}.zip"
      hash = filebase64sha256("${local.lambda_dir}/${name}.zip")
    }
  }
}

# --- Lambda deps layer (PyJWT + cryptography + stripe, rebuilt only on dep changes) ---

resource "null_resource" "lambda_layer_build" {
  triggers = {
    script_hash = filemd5("${local.project_root}/scripts/build_lambda_layer.sh")
  }

  provisioner "local-exec" {
    working_dir = local.project_root
    command     = "bash scripts/build_lambda_layer.sh"
  }
}

resource "aws_lambda_layer_version" "deps" {
  layer_name          = "${var.project}-${var.environment}-deps"
  filename            = "${local.project_root}/builds/lambda_layer.zip"
  source_code_hash    = filebase64sha256("${local.project_root}/scripts/build_lambda_layer.sh")
  compatible_runtimes = ["python3.12"]
  depends_on          = [null_resource.lambda_layer_build]
}
