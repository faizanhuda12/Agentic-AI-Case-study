# Vertex AI Vector Search Index and Endpoint Module

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Vertex AI resources"
  type        = string
  default     = "us-central1"
}

variable "index_name" {
  description = "Name of the Vertex AI Vector Search index"
  type        = string
  default     = "fedex-sops-index"
}

variable "index_description" {
  description = "Description of the index"
  type        = string
  default     = "Vector search index for FedEx SOPs"
}

variable "dimensions" {
  description = "Dimension of the embedding vectors"
  type        = number
  default     = 768  # Default for text-embedding-004 model
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
  validation {
    condition     = contains(["DOT_PRODUCT_DISTANCE", "EUCLIDEAN_DISTANCE", "COSINE_DISTANCE"], var.distance_measure_type)
    error_message = "distance_measure_type must be one of: DOT_PRODUCT_DISTANCE, EUCLIDEAN_DISTANCE, COSINE_DISTANCE"
  }
}

variable "index_update_method" {
  description = "The update method to use with this Index"
  type        = string
  default     = "BATCH_UPDATE"
  validation {
    condition     = contains(["BATCH_UPDATE", "STREAM_UPDATE"], var.index_update_method)
    error_message = "index_update_method must be either BATCH_UPDATE or STREAM_UPDATE"
  }
}

variable "endpoint_name" {
  description = "Name of the Vertex AI Vector Search endpoint"
  type        = string
  default     = "fedex-sops-endpoint"
}

variable "endpoint_description" {
  description = "Description of the endpoint"
  type        = string
  default     = "Vector search endpoint for FedEx SOPs"
}

variable "network" {
  description = "The full name of the Google Compute Engine network to which the index endpoint should be peered"
  type        = string
  default     = null
}

variable "enable_public_endpoint" {
  description = "If true, the endpoint will be accessible from the internet"
  type        = bool
  default     = true
}

# Enable required APIs
resource "google_project_service" "vertex_ai_api" {
  project = var.project_id
  service = "aiplatform.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "servicenetworking_api" {
  count   = var.network != null ? 1 : 0
  project = var.project_id
  service = "servicenetworking.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "storage_api" {
  project = var.project_id
  service = "storage-component.googleapis.com"

  disable_on_destroy = false
}

# Create GCS bucket for Vertex AI index
resource "google_storage_bucket" "index_bucket" {
  name          = "${var.project_id}-vertex-ai-index"
  location      = var.region
  project       = var.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  depends_on = [
    google_project_service.storage_api
  ]
}

# Vertex AI Vector Search Index
resource "google_vertex_ai_index" "sops_index" {
  project     = var.project_id
  region      = var.region
  display_name = var.index_name
  description  = var.index_description

  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.index_bucket.name}/sops-index"
    config {
      dimensions                  = var.dimensions
      approximate_neighbors_count = var.approximate_neighbors_count
      distance_measure_type       = var.distance_measure_type
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }

  index_update_method = var.index_update_method

  depends_on = [
    google_project_service.vertex_ai_api,
    google_storage_bucket.index_bucket
  ]
}

# Vertex AI Index Endpoint
resource "google_vertex_ai_index_endpoint" "sops_endpoint" {
  project      = var.project_id
  region       = var.region
  display_name = var.endpoint_name
  description  = var.endpoint_description

  network = var.network

  depends_on = [
    google_project_service.vertex_ai_api,
    google_project_service.servicenetworking_api
  ]
}

# Deploy Index to Endpoint
resource "google_vertex_ai_index_endpoint_deployed_index" "sops_deployed_index" {
  index_endpoint    = google_vertex_ai_index_endpoint.sops_endpoint.id
  index             = google_vertex_ai_index.sops_index.id
  deployed_index_id = "${replace(var.index_name, "-", "_")}_deployed"
  display_name      = "${var.index_name}-deployed"
  
  enable_access_logging = false

  automatic_resources {
    min_replica_count = 1
    max_replica_count = 1
  }

  depends_on = [
    google_vertex_ai_index.sops_index,
    google_vertex_ai_index_endpoint.sops_endpoint
  ]
}

# Outputs
output "index_id" {
  description = "The ID of the Vertex AI Index"
  value       = google_vertex_ai_index.sops_index.id
}

output "index_name" {
  description = "The name of the Vertex AI Index"
  value       = google_vertex_ai_index.sops_index.name
}

output "endpoint_id" {
  description = "The ID of the Vertex AI Index Endpoint"
  value       = google_vertex_ai_index_endpoint.sops_endpoint.id
}

output "endpoint_name" {
  description = "The name of the Vertex AI Index Endpoint"
  value       = google_vertex_ai_index_endpoint.sops_endpoint.name
}

output "deployed_index_id" {
  description = "The ID of the deployed index"
  value       = google_vertex_ai_index_endpoint_deployed_index.sops_deployed_index.deployed_index_id
}


