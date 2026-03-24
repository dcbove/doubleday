provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = var.project
    }
  }
}

module "oidc" {
  source                = "../../modules/oidc"
  project               = var.project
  region                = var.region
  github_repo           = "dcbove/doubleday"
  state_bucket          = var.state_bucket
  lock_table            = var.lock_table
  athena_results_bucket = var.athena_results_bucket
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions OIDC role"
  value       = module.oidc.role_arn
}
