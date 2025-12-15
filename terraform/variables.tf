# Main Terraform variables

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for resources"
  type        = string
  default     = "us-central1"
}

variable "index_name" {
  description = "Name of the Vertex AI Vector Search index"
  type        = string
  default     = "fedex-sops-index"
}

variable "endpoint_name" {
  description = "Name of the Vertex AI Vector Search endpoint"
  type        = string
  default     = "fedex-sops-endpoint"
}

variable "embedding_dimensions" {
  description = "Dimension of the embedding vectors (768 for text-embedding-004)"
  type        = number
  default     = 768
}

variable "approximate_neighbors_count" {
  description = "The default number of neighbors to find via approximate search"
  type        = number
  default     = 10
}

variable "distance_measure_type" {
  description = "The distance measure used in nearest neighbor search"
  type        = string
  default     = "DOT_PRODUCT_DISTANCE"
}

variable "index_update_method" {
  description = "The update method to use with this Index"
  type        = string
  default     = "BATCH_UPDATE"
}

variable "network" {
  description = "The full name of the Google Compute Engine network to which the index endpoint should be peered (optional)"
  type        = string
  default     = null
}

variable "enable_public_endpoint" {
  description = "If true, the endpoint will be accessible from the internet"
  type        = bool
  default     = true
}

# Cloud Run API Variables
variable "api_service_name" {
  description = "Name of the Cloud Run service for FastAPI"
  type        = string
  default     = "fedex-api"
}

variable "api_image" {
  description = "Container image URL for the FastAPI service"
  type        = string
  default     = "gcr.io/PROJECT_ID/fedex-api:latest"
}

variable "api_cpu" {
  description = "CPU allocation for Cloud Run service"
  type        = string
  default     = "1"
}

variable "api_memory" {
  description = "Memory allocation for Cloud Run service"
  type        = string
  default     = "512Mi"
}

variable "api_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 0
}

variable "api_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

# Frontend Variables
variable "frontend_bucket_name" {
  description = "Name of the GCS bucket for frontend (optional, will be auto-generated if not provided)"
  type        = string
  default     = null
}

variable "enable_frontend_cdn" {
  description = "Enable Cloud CDN for frontend"
  type        = bool
  default     = true
}

