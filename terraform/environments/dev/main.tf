provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
    }
  }
}

module "s3" {
  source      = "../../modules/s3"
  project     = var.project
  environment = var.environment
}
