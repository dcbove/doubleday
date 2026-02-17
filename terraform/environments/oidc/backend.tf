terraform {
  backend "s3" {
    bucket         = "appleforge-terraform-state"
    key            = "doubleday/oidc/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "appleforge-terraform-locks"
    encrypt        = true
  }
}
