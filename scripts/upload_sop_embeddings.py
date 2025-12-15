"""
Upload SOP Embeddings to Vertex AI Vector Search

This script:
1. Reads all SOP files from the sops/ directory
2. Generates embeddings using text-embedding-004
3. Creates a JSON file for batch upload to Vector Search
4. Uploads the embeddings to the Vector Search index via GCS
"""

import os
import json
import uuid
from typing import List, Dict
from google.cloud import storage
from google.cloud import aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel


def get_sop_files(sops_dir: str = "sops") -> Dict[str, str]:
    """Read all SOP files and return their contents."""
    sops = {}
    for filename in os.listdir(sops_dir):
        if filename.endswith('.txt'):
            filepath = os.path.join(sops_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Use filename without extension as ID
                sop_id = filename.replace('.txt', '')
                sops[sop_id] = content
    return sops


def generate_embeddings(texts: List[str], model: TextEmbeddingModel) -> List[List[float]]:
    """Generate embeddings for a list of texts."""
    embeddings = model.get_embeddings(texts)
    return [embedding.values for embedding in embeddings]


def create_jsonl_for_vector_search(sops: Dict[str, str], embeddings: Dict[str, List[float]]) -> List[Dict]:
    """Create JSONL format required by Vertex AI Vector Search batch update."""
    jsonl_data = []
    
    for sop_id, content in sops.items():
        # Map SOP ID to exception type for filtering
        exception_type_map = {
            'access_issue': 'Access Issue',
            'address_invalid': 'Address Invalid',
            'customer_not_home': 'Customer Not Home',
            'driver_issue': 'Driver Issue',
            'hub_delay': 'Hub Delay',
            'misroute': 'Misroute',
            'package_damage': 'Package Damage',
            'system_error': 'System Error',
            'unknown': 'Unknown',
            'weather_delay': 'Weather Delay'
        }
        
        exception_type = exception_type_map.get(sop_id, sop_id.replace('_', ' ').title())
        
        # Create datapoint in Vector Search format
        datapoint = {
            "id": f"sop_{sop_id}",
            "embedding": embeddings[sop_id],
            "restricts": [
                {
                    "namespace": "exception_type",
                    "allow": [exception_type]
                }
            ],
            "crowding_tag": sop_id
        }
        
        jsonl_data.append(datapoint)
    
    return jsonl_data


def upload_to_gcs(data: List[Dict], bucket_name: str, directory_prefix: str) -> str:
    """Upload JSONL data to GCS as a directory with individual files."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    # Upload as a single JSONL file in the directory
    # The directory path for Vertex AI must end with /
    blob_name = f"{directory_prefix}/embeddings.json"
    blob = bucket.blob(blob_name)
    
    # Convert to JSONL format (one JSON object per line)
    jsonl_content = '\n'.join(json.dumps(item) for item in data)
    
    blob.upload_from_string(jsonl_content, content_type='application/json')
    
    # Return the directory path (without trailing /)
    return f"gs://{bucket_name}/{directory_prefix}"


def trigger_index_update(project_id: str, region: str, index_id: str, gcs_uri: str):
    """Trigger a batch update of the Vector Search index."""
    aiplatform.init(project=project_id, location=region)
    
    # Get the index
    index = aiplatform.MatchingEngineIndex(index_name=index_id)
    
    # Update the index from GCS
    print(f"Updating index {index_id} from {gcs_uri}...")
    index.update_embeddings(
        contents_delta_uri=gcs_uri,
        is_complete_overwrite=True  # Replace all existing datapoints
    )
    
    print("Index update initiated. This may take several minutes.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload SOP embeddings to Vertex AI Vector Search")
    parser.add_argument("--project-id", required=True, help="GCP Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument("--index-id", required=True, help="Vertex AI Index ID (numeric or full path)")
    parser.add_argument("--bucket-name", help="GCS bucket for embeddings (default: {project-id}-vertex-ai-index)")
    parser.add_argument("--sops-dir", default="sops", help="Directory containing SOP files")
    
    args = parser.parse_args()
    
    # Initialize Vertex AI
    vertexai.init(project=args.project_id, location=args.region)
    aiplatform.init(project=args.project_id, location=args.region)
    
    bucket_name = args.bucket_name or f"{args.project_id}-vertex-ai-index"
    
    print("="*60)
    print("SOP Embeddings Upload to Vertex AI Vector Search")
    print("="*60)
    print(f"Project: {args.project_id}")
    print(f"Region: {args.region}")
    print(f"Index ID: {args.index_id}")
    print(f"Bucket: {bucket_name}")
    print(f"SOPs Directory: {args.sops_dir}")
    print()
    
    # Step 1: Read SOP files
    print("[1/5] Reading SOP files...")
    sops = get_sop_files(args.sops_dir)
    print(f"   Found {len(sops)} SOP files:")
    for sop_id in sops:
        print(f"   - {sop_id}")
    print()
    
    # Step 2: Generate embeddings
    print("[2/5] Generating embeddings using text-embedding-004...")
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    
    embeddings = {}
    for sop_id, content in sops.items():
        # Generate embedding for the SOP content
        embedding = generate_embeddings([content], model)[0]
        embeddings[sop_id] = embedding
        print(f"   OK: Generated embedding for {sop_id} (dimension: {len(embedding)})")
    print()
    
    # Step 3: Create JSONL format
    print("[3/5] Creating JSONL format for Vector Search...")
    jsonl_data = create_jsonl_for_vector_search(sops, embeddings)
    print(f"   Created {len(jsonl_data)} datapoints")
    print()
    
    # Step 4: Upload to GCS
    directory_prefix = "embeddings"
    print(f"[4/5] Uploading to GCS: gs://{bucket_name}/{directory_prefix}/...")
    gcs_uri = upload_to_gcs(jsonl_data, bucket_name, directory_prefix)
    print(f"   OK: Uploaded to {gcs_uri}")
    print()
    
    # Step 5: Trigger index update
    print("[5/5] Triggering Vector Search index update...")
    try:
        trigger_index_update(args.project_id, args.region, args.index_id, gcs_uri)
        print("   OK: Index update initiated!")
    except Exception as e:
        print(f"   WARNING: Error triggering index update: {e}")
        print("   You may need to manually trigger the update from the GCP Console.")
    
    print()
    print("="*60)
    print("SUCCESS: Embedding upload complete!")
    print("="*60)
    print(f"GCS URI: {gcs_uri}")
    print(f"Index ID: {args.index_id}")
    print()
    print("Note: The index update may take 5-30 minutes to complete.")
    print("You can monitor the progress in the GCP Console under Vertex AI > Vector Search.")


if __name__ == "__main__":
    main()

