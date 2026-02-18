locals {
  project_root = "${path.module}/../../.."
}

resource "null_resource" "lambda_package_build" {
  triggers = {
    deps_hash     = filemd5("${local.project_root}/uv.lock")
    src_hash      = sha1(join("", [for f in sort(fileset("${local.project_root}/src", "doubleday/**/*.py")) : filemd5("${local.project_root}/src/${f}")]))
    sql_pipe_hash = sha1(join("", [for f in sort(fileset("${local.project_root}/sql/pipeline", "*.sql")) : filemd5("${local.project_root}/sql/pipeline/${f}")]))
    sql_api_hash  = sha1(join("", [for f in sort(fileset("${local.project_root}/sql/api", "*.sql")) : filemd5("${local.project_root}/sql/api/${f}")]))
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
