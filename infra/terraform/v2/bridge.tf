# ──────────────────────────────────────────────────────────────
# Materalle-2 V2 — WebSocket Bridge
# API Gateway WebSocket API + Lambda + DynamoDB connections.
# Relays envelopes between SPA (frontend) and local Django backend.
# ──────────────────────────────────────────────────────────────

variable "backend_shared_secret" {
  description = "Shared secret used by the local backend to authenticate its $connect."
  type        = string
  sensitive   = true
}

# ── DynamoDB: active WebSocket connections ──────────────────
resource "aws_dynamodb_table" "ws_connections" {
  name         = "${local.name_prefix}-ws-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connection_id"

  attribute {
    name = "connection_id"
    type = "S"
  }

  attribute {
    name = "role"
    type = "S"
  }

  attribute {
    name = "user_sub"
    type = "S"
  }

  global_secondary_index {
    name            = "role-index"
    hash_key        = "role"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "role-user-index"
    hash_key        = "role"
    range_key       = "user_sub"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = { Name = "${local.name_prefix}-ws-connections" }
}

# ── Secret for backend WS auth ───────────────────────────────
resource "aws_secretsmanager_secret" "backend_ws_secret" {
  name = "${local.name_prefix}/backend-ws-secret"
}

resource "aws_secretsmanager_secret_version" "backend_ws_secret" {
  secret_id     = aws_secretsmanager_secret.backend_ws_secret.id
  secret_string = var.backend_shared_secret
}

# ── Lambda package (code + python-jose deps) ────────────────
resource "null_resource" "bridge_lambda_deps" {
  triggers = {
    requirements = filesha256("${path.module}/lambda/bridge/requirements.txt")
    handler      = filesha256("${path.module}/lambda/bridge/handler.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      cd ${path.module}/lambda/bridge
      rm -rf build
      mkdir -p build
      cp handler.py build/
      pip install -r requirements.txt -t build/ --quiet --upgrade
    EOT
  }
}

data "archive_file" "bridge_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/bridge/build"
  output_path = "${path.module}/lambda/bridge/bridge.zip"
  depends_on  = [null_resource.bridge_lambda_deps]
}

# ── Lambda execution role ───────────────────────────────────
resource "aws_iam_role" "bridge_lambda" {
  name = "${local.name_prefix}-bridge-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "bridge_lambda_basic" {
  role       = aws_iam_role.bridge_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "bridge_lambda_inline" {
  name = "${local.name_prefix}-bridge-lambda-inline"
  role = aws_iam_role.bridge_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
        ]
        Resource = [
          aws_dynamodb_table.ws_connections.arn,
          "${aws_dynamodb_table.ws_connections.arn}/index/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["execute-api:ManageConnections"]
        Resource = "arn:aws:execute-api:${var.aws_region}:*:*/*/*"
      },
    ]
  })
}

# ── Lambda function ─────────────────────────────────────────
resource "aws_cloudwatch_log_group" "bridge_lambda" {
  name              = "/aws/lambda/${local.name_prefix}-bridge"
  retention_in_days = 14
}

resource "aws_lambda_function" "bridge" {
  function_name    = "${local.name_prefix}-bridge"
  role             = aws_iam_role.bridge_lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  filename         = data.archive_file.bridge_lambda.output_path
  source_code_hash = data.archive_file.bridge_lambda.output_base64sha256

  environment {
    variables = {
      AWS_REGION_NAME       = var.aws_region
      COGNITO_USER_POOL_ID  = aws_cognito_user_pool.main.id
      COGNITO_APP_CLIENT_ID = aws_cognito_user_pool_client.spa.id
      CONNECTIONS_TABLE     = aws_dynamodb_table.ws_connections.name
      BACKEND_SHARED_SECRET = var.backend_shared_secret
    }
  }

  depends_on = [aws_cloudwatch_log_group.bridge_lambda]
}

# ── API Gateway WebSocket API ───────────────────────────────
resource "aws_apigatewayv2_api" "ws" {
  name                       = "${local.name_prefix}-ws"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
}

resource "aws_apigatewayv2_integration" "ws_lambda" {
  api_id                    = aws_apigatewayv2_api.ws.id
  integration_type          = "AWS_PROXY"
  integration_uri           = aws_lambda_function.bridge.invoke_arn
  integration_method        = "POST"
  content_handling_strategy = "CONVERT_TO_TEXT"
}

resource "aws_apigatewayv2_route" "connect" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.ws_lambda.id}"
}

resource "aws_apigatewayv2_route" "disconnect" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.ws_lambda.id}"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.ws.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.ws_lambda.id}"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.ws.id
  name        = "prod"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 500
    throttling_rate_limit  = 200
  }
}

resource "aws_lambda_permission" "ws_invoke" {
  statement_id  = "AllowExecutionFromAPIGatewayWebSocket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bridge.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws.execution_arn}/*/*"
}

# ── Outputs ─────────────────────────────────────────────────
output "v2_ws_endpoint" {
  value       = "${aws_apigatewayv2_api.ws.api_endpoint}/${aws_apigatewayv2_stage.prod.name}"
  description = "WebSocket endpoint for frontend and local backend"
}

output "v2_ws_connections_table" {
  value       = aws_dynamodb_table.ws_connections.name
  description = "DynamoDB table holding active WS connections"
}

output "v2_backend_ws_secret_arn" {
  value       = aws_secretsmanager_secret.backend_ws_secret.arn
  description = "Secrets Manager ARN for the backend shared secret"
  sensitive   = true
}
