terraform {
  backend "s3" {
    bucket  = "ptab-tf-state-604881392797"
    key     = "ptab-intelligence/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  required_version = ">= 1.5.0"
}

provider "aws" {
  region  = var.aws_region
  profile = "ptab"

  default_tags {
    tags = {
      Project     = "ptab-intelligence"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
