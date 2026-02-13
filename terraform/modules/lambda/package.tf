data "archive_file" "lambda_package" {
  type        = "zip"
  output_path = "${path.module}/../../../builds/lambda_package.zip"

  dynamic "source" {
    for_each = fileset("${path.module}/../../../src", "doubleday/**/*.py")
    content {
      content  = file("${path.module}/../../../src/${source.value}")
      filename = source.value
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/../../../sql/pipeline", "*.sql")
    content {
      content  = file("${path.module}/../../../sql/pipeline/${source.value}")
      filename = "doubleday/sql/${source.value}"
    }
  }
}
