"""
Load FedEx SOPs into Vertex AI Vector Search

This script:
1. Reads all SOP files from the sops/ directory
2. Generates embeddings using Vertex AI text-embedding-004 model
3. Loads embeddings into Vertex AI Vector Search index
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from google.cloud import aiplatform
from google.cloud.aiplatform import vector_search
from vertexai.preview.language_models import TextEmbeddingModel
import vertexai


class SOPsVectorDBLoader:
    """Class to load SOPs into Vertex AI Vector Search."""
    
    def __init__(self, project_id: str, region: str, index_id: str, endpoint_id: str):
        """
        Initialize the loader.
        
        Args:
            project_id: GCP Project ID
            region: GCP Region
            index_id: Vertex AI Index ID
            endpoint_id: Vertex AI Index Endpoint ID
        """
        self.project_id = project_id
        self.region = region
        self.index_id = index_id
        self.endpoint_id = endpoint_id
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=region)
        aiplatform.init(project=project_id, location=region)
        
        # Initialize embedding model
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        
        print(f"✅ Initialized SOPs Vector DB Loader")
        print(f"   Project: {project_id}")
        print(f"   Region: {region}")
        print(f"   Index ID: {index_id}")
        print(f"   Endpoint ID: {endpoint_id}")
    
    def read_sop_files(self, sops_dir: str = "sops") -> List[Dict[str, str]]:
        """
        Read all SOP files from the directory.
        
        Args:
            sops_dir: Directory containing SOP files
            
        Returns:
            List of dictionaries with 'filename', 'exception_type', and 'content'
        """
        sops_path = Path(sops_dir)
        if not sops_path.exists():
            raise FileNotFoundError(f"SOPs directory not found: {sops_dir}")
        
        sops = []
        for sop_file in sops_path.glob("*.txt"):
            exception_type = sop_file.stem.replace("_", " ").title()
            
            with open(sop_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sops.append({
                'filename': sop_file.name,
                'exception_type': exception_type,
                'content': content
            })
            
            print(f"📄 Loaded: {sop_file.name} ({len(content)} chars)")
        
        return sops
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        print(f"🔄 Generating embeddings for {len(texts)} texts...")
        
        # Generate embeddings in batches
        batch_size = 5  # Vertex AI allows up to 5 texts per request
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self.embedding_model.get_embeddings(batch)
            
            # Extract embedding values
            batch_embeddings = [emb.values for emb in embeddings]
            all_embeddings.extend(batch_embeddings)
            
            print(f"   Generated embeddings for batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            time.sleep(0.1)  # Small delay to avoid rate limits
        
        print(f"✅ Generated {len(all_embeddings)} embeddings")
        return all_embeddings
    
    def prepare_datapoints(self, sops: List[Dict[str, str]], embeddings: List[List[float]]) -> List[Dict[str, Any]]:
        """
        Prepare datapoints for Vertex AI Vector Search.
        
        Args:
            sops: List of SOP dictionaries
            embeddings: List of embedding vectors
            
        Returns:
            List of datapoint dictionaries
        """
        datapoints = []
        
        for sop, embedding in zip(sops, embeddings):
            datapoint = {
                "datapoint_id": f"sop_{sop['filename'].replace('.txt', '')}",
                "feature_vector": embedding,
                "restricts": [
                    {
                        "namespace": "exception_type",
                        "allow_list": [sop['exception_type']]
                    }
                ]
            }
            datapoints.append(datapoint)
        
        return datapoints
    
    def load_to_index(self, datapoints: List[Dict[str, Any]], gcs_bucket: str = None):
        """
        Load datapoints into the Vertex AI Vector Search index.
        
        Vertex AI Vector Search requires batch upload via GCS. This method:
        1. Formats datapoints as JSONL
        2. Uploads to GCS bucket
        3. Triggers batch update
        
        Args:
            datapoints: List of datapoint dictionaries
            gcs_bucket: GCS bucket name for batch upload (optional)
        """
        print(f"📤 Preparing {len(datapoints)} datapoints for upload...")
        
        # Format datapoints as JSONL
        import json
        jsonl_lines = []
        for dp in datapoints:
            jsonl_lines.append(json.dumps(dp))
        
        jsonl_content = '\n'.join(jsonl_lines)
        
        if gcs_bucket:
            # Upload to GCS and trigger batch update
            try:
                from google.cloud import storage
                
                # Initialize GCS client
                storage_client = storage.Client(project=self.project_id)
                bucket = storage_client.bucket(gcs_bucket)
                
                # Upload JSONL file
                blob_name = f"vertex-ai-index/sops-datapoints-{int(time.time())}.jsonl"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(jsonl_content, content_type='application/jsonl')
                
                print(f"✅ Uploaded datapoints to gs://{gcs_bucket}/{blob_name}")
                
                # Trigger batch update
                index = aiplatform.MatchingEngineIndex(index_name=self.index_id)
                index.update_embeddings(
                    contents_delta_uri=f"gs://{gcs_bucket}/{blob_name}"
                )
                
                print(f"✅ Triggered batch update for index")
                print(f"   Monitor progress in Vertex AI Console")
                
            except ImportError:
                print("⚠️  google-cloud-storage not installed. Install with: pip install google-cloud-storage")
                print("   Falling back to manual upload instructions...")
                gcs_bucket = None
        
        if not gcs_bucket:
            # Save to local file for manual upload
            output_file = "sops_datapoints.jsonl"
            with open(output_file, 'w') as f:
                f.write(jsonl_content)
            
            print(f"✅ Saved datapoints to {output_file}")
            print(f"\n📋 Next steps:")
            print(f"   1. Upload {output_file} to a GCS bucket:")
            print(f"      gsutil cp {output_file} gs://YOUR_BUCKET/vertex-ai-index/")
            print(f"   2. Trigger batch update:")
            print(f"      gcloud ai indexes update-embeddings {self.index_id} \\")
            print(f"        --contents-delta-uri=gs://YOUR_BUCKET/vertex-ai-index/{output_file} \\")
            print(f"        --region={self.region}")
            print(f"\n   Or use the Vertex AI Console to upload and update")
    
    def run(self, sops_dir: str = "sops"):
        """
        Run the complete loading process.
        
        Args:
            sops_dir: Directory containing SOP files
        """
        print("="*60)
        print("FedEx SOPs Vector DB Loader")
        print("="*60)
        
        # Read SOPs
        print("\n1. Reading SOP files...")
        sops = self.read_sop_files(sops_dir)
        print(f"✅ Read {len(sops)} SOP files")
        
        # Extract texts
        texts = [sop['content'] for sop in sops]
        
        # Generate embeddings
        print("\n2. Generating embeddings...")
        embeddings = self.generate_embeddings(texts)
        
        # Prepare datapoints
        print("\n3. Preparing datapoints...")
        datapoints = self.prepare_datapoints(sops, embeddings)
        
        # Load to index
        print("\n4. Loading to Vector Search index...")
        gcs_bucket = getattr(self, '_gcs_bucket', None)
        self.load_to_index(datapoints, gcs_bucket=gcs_bucket)
        
        print("\n" + "="*60)
        print("✅ Loading process completed!")
        print("="*60)
        print("\nNext steps:")
        print("1. Upload datapoints to GCS bucket")
        print("2. Trigger batch update via Vertex AI API or console")
        print("3. Wait for index update to complete")
        print("4. Test queries using the RAG retrieval module")


def main():
    """Main function - update with your GCP details."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load SOPs into Vertex AI Vector Search")
    parser.add_argument("--project-id", required=True, help="GCP Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument("--index-id", required=True, help="Vertex AI Index ID")
    parser.add_argument("--endpoint-id", required=True, help="Vertex AI Index Endpoint ID")
    parser.add_argument("--sops-dir", default="sops", help="Directory containing SOP files")
    parser.add_argument("--gcs-bucket", help="GCS bucket for batch upload (optional)")
    
    args = parser.parse_args()
    
    # Initialize loader
    loader = SOPsVectorDBLoader(
        project_id=args.project_id,
        region=args.region,
        index_id=args.index_id,
        endpoint_id=args.endpoint_id
    )
    
    # Set GCS bucket if provided
    if args.gcs_bucket:
        loader._gcs_bucket = args.gcs_bucket
    
    # Run loading process
    loader.run(sops_dir=args.sops_dir)


if __name__ == "__main__":
    main()

