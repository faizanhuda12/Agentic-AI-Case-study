# Cloud Storage + Cloud CDN for React Frontend

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "bucket_name" {
  description = "Name of the GCS bucket for frontend"
  type        = string
  default     = null
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "enable_cdn" {
  description = "Enable Cloud CDN"
  type        = bool
  default     = true
}

# Enable required APIs
resource "google_project_service" "storage_api" {
  project = var.project_id
  service = "storage-component.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cdn_api" {
  count   = var.enable_cdn ? 1 : 0
  project = var.project_id
  service = "cloudbilling.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute_api" {
  count   = var.enable_cdn ? 1 : 0
  project = var.project_id
  service = "compute.googleapis.com"
  disable_on_destroy = false
}

# Generate bucket name if not provided
locals {
  bucket_name = var.bucket_name != null ? var.bucket_name : "${var.project_id}-fedex-frontend"
}

# Cloud Storage Bucket
resource "google_storage_bucket" "frontend" {
  name          = local.bucket_name
  location      = var.region
  project       = var.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  depends_on = [
    google_project_service.storage_api
  ]
}

# Make bucket publicly accessible
resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Cloud CDN Backend Bucket
resource "google_compute_backend_bucket" "frontend" {
  count       = var.enable_cdn ? 1 : 0
  name        = "${local.bucket_name}-backend"
  description = "Backend bucket for frontend CDN"
  bucket_name = google_storage_bucket.frontend.name
  enable_cdn  = true

  depends_on = [
    google_project_service.compute_api
  ]
}

# Outputs
output "bucket_name" {
  description = "Name of the GCS bucket"
  value       = google_storage_bucket.frontend.name
}

output "bucket_url" {
  description = "URL of the GCS bucket"
  value       = "gs://${google_storage_bucket.frontend.name}"
}

output "website_url" {
  description = "Website URL for the bucket"
  value       = "https://storage.googleapis.com/${google_storage_bucket.frontend.name}/index.html"
}

output "cdn_backend_bucket" {
  description = "CDN backend bucket name"
  value       = var.enable_cdn ? google_compute_backend_bucket.frontend[0].name : null
}


