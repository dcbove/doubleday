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

module "glue" {
  source                = "../../modules/glue"
  project               = var.project
  environment           = var.environment
  lakehouse_bucket_name = module.s3.lakehouse_bucket_name
}
