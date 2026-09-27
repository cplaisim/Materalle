# ──────────────────────────────────────────────────────────────
# Materalle-2 V2 — Root Module
# Independent of the legacy ECS stack in ../main.tf.
# Resources: Cognito User Pool + WebSocket bridge (API GW + Lambda + DynamoDB).
# State lives in its own directory/backend.
# ──────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }

  # Uncomment when you want remote state:
  # backend "s3" {
  #   bucket = "materalle-terraform-state"
  #   key    = "v2/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ────────────────────────────────────────────────

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "materalle"
}

variable "environment" {
  type    = string
  default = "prod"
}

locals {
  name_prefix = "${var.project}-${var.environment}"
}
