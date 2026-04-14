# ── S3: PTAB document storage ─────────────────────────────────────────────────
resource "aws_s3_bucket" "ptab_docs" {
  bucket = "ptab-documents-${var.account_id}"
}

resource "aws_s3_bucket_versioning" "ptab_docs" {
  bucket = aws_s3_bucket.ptab_docs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ptab_docs" {
  bucket = aws_s3_bucket.ptab_docs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "ptab_docs" {
  bucket                  = aws_s3_bucket.ptab_docs.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# ── Secrets Manager ───────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "pinecone" {
  name                    = "ptab/pinecone-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "pinecone" {
  secret_id     = aws_secretsmanager_secret.pinecone.id
  secret_string = var.pinecone_api_key
}

resource "aws_secretsmanager_secret" "anthropic" {
  name                    = "ptab/anthropic-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "anthropic" {
  secret_id     = aws_secretsmanager_secret.anthropic.id
  secret_string = var.anthropic_api_key
}

# ── IAM: Lambda execution role ────────────────────────────────────────────────
resource "aws_iam_role" "lambda_exec" {
  name = "ptab-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "ptab-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:${var.account_id}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.ptab_docs.arn, "${aws_s3_bucket.ptab_docs.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.pinecone.arn, aws_secretsmanager_secret.anthropic.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1"
      }
    ]
  })
}

# ── ECR: Container registry ───────────────────────────────────────────────────
resource "aws_ecr_repository" "ptab_rag" {
  name                 = "ptab-rag"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }
}

# ── Lambda: RAG query function ────────────────────────────────────────────────
resource "aws_lambda_function" "rag_query" {
  function_name = "ptab-rag-query"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.ptab_rag.repository_url}:latest"
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      PINECONE_SECRET_ARN  = aws_secretsmanager_secret.pinecone.arn
      ANTHROPIC_SECRET_ARN = aws_secretsmanager_secret.anthropic.arn
      PINECONE_INDEX_NAME  = var.pinecone_index_name
      S3_BUCKET            = aws_s3_bucket.ptab_docs.id
      AWS_REGION_NAME      = var.aws_region
    }
  }

  depends_on = [aws_ecr_repository.ptab_rag]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# ── API Gateway ───────────────────────────────────────────────────────────────
resource "aws_apigatewayv2_api" "ptab_api" {
  name          = "ptab-intelligence-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
  }
}

resource "aws_apigatewayv2_integration" "rag_query" {
  api_id             = aws_apigatewayv2_api.ptab_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.rag_query.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "query" {
  api_id    = aws_apigatewayv2_api.ptab_api.id
  route_key = "POST /query"
  target    = "integrations/${aws_apigatewayv2_integration.rag_query.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.ptab_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rag_query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ptab_api.execution_arn}/*/*"
}
