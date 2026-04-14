output "api_gateway_url" {
  description = "PTAB Intelligence API endpoint"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "docs_bucket" {
  description = "S3 bucket for PTAB documents"
  value       = aws_s3_bucket.ptab_docs.id
}

output "ecr_repository_url" {
  description = "ECR repository URL for RAG Lambda image"
  value       = aws_ecr_repository.ptab_rag.repository_url
}

output "lambda_function_name" {
  description = "RAG query Lambda function name"
  value       = aws_lambda_function.rag_query.function_name
}
