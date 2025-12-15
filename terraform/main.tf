# Main Terraform configuration for FedEx Exception Classification System

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Provider configuration
provider "google" {
  project = var.project_id
  region  = var.region
}

# Vertex AI Vector Search Module
module "vertex_ai_vector_search" {
  source = "./modules/vertex-ai-vector-search"

  project_id = var.project_id
  region     = var.region

  index_name        = var.index_name
  index_description = "Vector search index for FedEx Standard Operating Procedures"
  endpoint_name     = var.endpoint_name
  endpoint_description = "Vector search endpoint for FedEx SOPs RAG retrieval"
  
  dimensions                  = var.embedding_dimensions
  approximate_neighbors_count = var.approximate_neighbors_count
  distance_measure_type       = var.distance_measure_type
  index_update_method         = var.index_update_method

  network              = var.network
  enable_public_endpoint = var.enable_public_endpoint
}

# Cloud Run for FastAPI Backend
module "cloud_run_api" {
  source = "./modules/cloud-run"

  project_id  = var.project_id
  region      = var.region
  service_name = var.api_service_name
  image       = var.api_image
  port        = 8000
  cpu         = var.api_cpu
  memory      = var.api_memory
  min_instances = var.api_min_instances
  max_instances = var.api_max_instances
  allow_unauthenticated = true

  environment_variables = {
    # Add any environment variables needed for the API
  }

  # Temporarily removed dependency to allow Cloud Run to be created first
  # depends_on = [
  #   module.vertex_ai_vector_search
  # ]
}

# Cloud Storage for React Frontend
module "cloud_storage_frontend" {
  source = "./modules/cloud-storage-frontend"

  project_id  = var.project_id
  region      = var.region
  bucket_name = var.frontend_bucket_name
  enable_cdn  = var.enable_frontend_cdn
}

