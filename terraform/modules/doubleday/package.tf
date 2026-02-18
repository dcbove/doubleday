locals {
  project_root = "${path.module}/../../.."
}

resource "null_resource" "lambda_deps" {
  triggers = {
    requirements = "PyJWT cryptography"
  }

  provisioner "local-exec" {
    working_dir = local.project_root
    command     = <<-EOT
      rm -rf builds/lambda_deps
      mkdir -p builds/lambda_deps
      pip install PyJWT cryptography \
        --target builds/lambda_deps \
        --platform manylinux2014_x86_64 \
        --only-binary=:all: \
        --python-version 3.12 \
        --quiet
    EOT
  }
}

resource "null_resource" "lambda_package_build" {
  triggers = {
    deps          = null_resource.lambda_deps.id
    src_hash      = sha1(join("", [for f in sort(fileset("${local.project_root}/src", "doubleday/**/*.py")) : filemd5("${local.project_root}/src/${f}")]))
    sql_pipe_hash = sha1(join("", [for f in sort(fileset("${local.project_root}/sql/pipeline", "*.sql")) : filemd5("${local.project_root}/sql/pipeline/${f}")]))
    sql_api_hash  = sha1(join("", [for f in sort(fileset("${local.project_root}/sql/api", "*.sql")) : filemd5("${local.project_root}/sql/api/${f}")]))
  }

  provisioner "local-exec" {
    working_dir = local.project_root
    command     = <<-EOT
      rm -rf builds/lambda_package
      mkdir -p builds/lambda_package/doubleday/sql/pipeline builds/lambda_package/doubleday/sql/api
      cp -r builds/lambda_deps/* builds/lambda_package/
      (cd src && find doubleday -name '*.py' | while IFS= read -r f; do
        mkdir -p "../builds/lambda_package/$(dirname "$f")"
        cp "$f" "../builds/lambda_package/$f"
      done)
      cp sql/pipeline/*.sql builds/lambda_package/doubleday/sql/pipeline/
      cp sql/api/*.sql builds/lambda_package/doubleday/sql/api/
    EOT
  }
}

data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = "${local.project_root}/builds/lambda_package"
  output_path = "${local.project_root}/builds/lambda_package.zip"
  depends_on  = [null_resource.lambda_package_build]
}
