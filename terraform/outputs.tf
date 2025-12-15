# Main Terraform outputs

output "vector_search_index_id" {
  description = "The ID of the Vertex AI Vector Search Index"
  value       = module.vertex_ai_vector_search.index_id
}

output "vector_search_index_name" {
  description = "The name of the Vertex AI Vector Search Index"
  value       = module.vertex_ai_vector_search.index_name
}

output "vector_search_endpoint_id" {
  description = "The ID of the Vertex AI Index Endpoint"
  value       = module.vertex_ai_vector_search.endpoint_id
}

output "vector_search_endpoint_name" {
  description = "The name of the Vertex AI Index Endpoint"
  value       = module.vertex_ai_vector_search.endpoint_name
}

output "deployed_index_id" {
  description = "The ID of the deployed index"
  value       = module.vertex_ai_vector_search.deployed_index_id
}

# Cloud Run API Outputs
output "api_service_url" {
  description = "URL of the Cloud Run API service"
  value       = module.cloud_run_api.service_url
}

output "api_service_name" {
  description = "Name of the Cloud Run API service"
  value       = module.cloud_run_api.service_name
}

# Frontend Outputs
output "frontend_bucket_name" {
  description = "Name of the GCS bucket for frontend"
  value       = module.cloud_storage_frontend.bucket_name
}

output "frontend_website_url" {
  description = "Website URL for the frontend"
  value       = module.cloud_storage_frontend.website_url
}

output "frontend_bucket_url" {
  description = "GCS bucket URL"
  value       = module.cloud_storage_frontend.bucket_url
}

