# ──────────────────────────────────────────────────────────────
# Materalle-2 V2 — Cognito User Pool
# Replaces auth_user + UserProfile + LLMSettings tables.
# Custom attributes carry role and LLM preferences.
# ──────────────────────────────────────────────────────────────

resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
    invite_message_template {
      email_subject = "Materalle — your account"
      email_message = "Welcome. Username: {username}. Temporary password: {####}"
      sms_message   = "Materalle: {username} / {####}"
    }
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # ── Custom attributes ────────────────────────────────────────
  schema {
    name                     = "role"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false
    string_attribute_constraints {
      min_length = 1
      max_length = 20
    }
  }

  schema {
    name                     = "llm_backend"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false
    string_attribute_constraints {
      min_length = 1
      max_length = 20
    }
  }

  schema {
    name                     = "ollama_model"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false
    string_attribute_constraints {
      min_length = 0
      max_length = 64
    }
  }

  schema {
    name                     = "admin_title"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false
    string_attribute_constraints {
      min_length = 0
      max_length = 100
    }
  }

  schema {
    name                     = "admin_department"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false
    string_attribute_constraints {
      min_length = 0
      max_length = 100
    }
  }

  # Standard attributes we want
  schema {
    name                     = "phone_number"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false
  }

  tags = {
    Name        = "${local.name_prefix}-users"
    Environment = var.environment
  }
}

# App client used by the Next.js SPA (public, no secret)
resource "aws_cognito_user_pool_client" "spa" {
  name         = "${local.name_prefix}-spa"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  allowed_oauth_flows_user_pool_client = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
  ]

  access_token_validity  = 60 # minutes
  id_token_validity      = 60 # minutes
  refresh_token_validity = 30 # days
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  read_attributes = [
    "email",
    "email_verified",
    "phone_number",
    "given_name",
    "family_name",
    "custom:role",
    "custom:llm_backend",
    "custom:ollama_model",
    "custom:admin_title",
    "custom:admin_department",
  ]

  write_attributes = [
    "email",
    "phone_number",
    "given_name",
    "family_name",
    "custom:llm_backend",
    "custom:ollama_model",
    "custom:admin_title",
    "custom:admin_department",
    # Note: custom:role is intentionally NOT writable by end users.
    # Only administrators can change roles (via AdminUpdateUserAttributes).
  ]
}

output "v2_cognito_user_pool_id" {
  value       = aws_cognito_user_pool.main.id
  description = "Cognito User Pool ID (for Amplify + Lambda JWT verification)"
}

output "v2_cognito_user_pool_arn" {
  value       = aws_cognito_user_pool.main.arn
  description = "Cognito User Pool ARN"
}

output "v2_cognito_spa_client_id" {
  value       = aws_cognito_user_pool_client.spa.id
  description = "Cognito App Client ID for the SPA"
}
