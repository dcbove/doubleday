locals {
  project_root = "${path.module}/../../.."
}

# --- Lambda code package (source + SQL only, no pip deps) ---

resource "null_resource" "lambda_package_build" {
  triggers = {
    src_hash      = sha1(join("", [for f in sort(fileset("${local.project_root}/src", "doubleday/**/*.py")) : filemd5("${local.project_root}/src/${f}")]))
    sql_pipe_hash = sha1(join("", [for f in sort(fileset("${local.project_root}/sql/pipeline", "*.sql")) : filemd5("${local.project_root}/sql/pipeline/${f}")]))
  }

  provisioner "local-exec" {
    working_dir = local.project_root
    command     = "bash scripts/build_lambda_package.sh"
  }
}

data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = "${local.project_root}/builds/lambda_package"
  output_path = "${local.project_root}/builds/lambda_package.zip"
  depends_on  = [null_resource.lambda_package_build]
}

# --- Lambda deps layer (PyJWT + cryptography, rebuilt only on dep changes) ---

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
