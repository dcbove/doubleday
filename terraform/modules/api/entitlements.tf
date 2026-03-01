resource "aws_dynamodb_table" "entitlements" {
  name         = "${var.project}-${var.environment}-entitlements"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "PK"

  attribute {
    name = "PK"
    type = "S"
  }

  deletion_protection_enabled = var.environment == "prod"
}
