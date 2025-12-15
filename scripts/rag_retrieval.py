"""
RAG (Retrieval-Augmented Generation) Module for SOP Retrieval

This module provides functionality to:
1. Query Vertex AI Vector Search for relevant SOPs
2. Retrieve top-k most relevant SOPs based on exception type
3. Format retrieved SOPs for use in agent workflows
"""

import os
from typing import List, Dict, Optional
from google.cloud import aiplatform
from vertexai.preview.language_models import TextEmbeddingModel
import vertexai


class SOPRetrievalAgent:
    """Agent for retrieving relevant SOPs using RAG."""
    
    def __init__(self, project_id: str, region: str, index_id: str, endpoint_id: str, deployed_index_id: str):
        """
        Initialize the SOP Retrieval Agent.
        
        Args:
            project_id: GCP Project ID
            region: GCP Region
            index_id: Vertex AI Index ID
            endpoint_id: Vertex AI Index Endpoint ID
            deployed_index_id: Deployed Index ID
        """
        self.project_id = project_id
        self.region = region
        self.index_id = index_id
        self.endpoint_id = endpoint_id
        self.deployed_index_id = deployed_index_id
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=region)
        aiplatform.init(project=project_id, location=region)
        
        # Initialize embedding model
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        
        # Initialize index endpoint
        self.index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=self.endpoint_id
        )
        
        print(f"✅ Initialized SOP Retrieval Agent")
        print(f"   Project: {project_id}")
        print(f"   Region: {region}")
        print(f"   Index ID: {index_id}")
        print(f"   Endpoint ID: {endpoint_id}")
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query string.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector
        """
        embeddings = self.embedding_model.get_embeddings([query])
        return embeddings[0].values
    
    def query_vector_search(self, query_embedding: List[float], 
                           num_neighbors: int = 3,
                           exception_type_filter: Optional[str] = None) -> List[Dict]:
        """
        Query the Vector Search index.
        
        Args:
            query_embedding: Query embedding vector
            num_neighbors: Number of nearest neighbors to retrieve
            exception_type_filter: Optional exception type to filter by
            
        Returns:
            List of retrieved SOP documents with scores
        """
        # Prepare restricts if filtering by exception type
        restricts = []
        if exception_type_filter:
            restricts = [{
                "namespace": "exception_type",
                "allow_list": [exception_type_filter]
            }]
        
        # Query the index
        try:
            # Note: Actual API may vary - this is a conceptual implementation
            # You may need to use the MatchingEngineIndexEndpoint.find_neighbors method
            results = self.index_endpoint.find_neighbors(
                deployed_index_id=self.deployed_index_id,
                queries=[query_embedding],
                num_neighbors=num_neighbors,
                restricts=restricts if restricts else None
            )
            
            # Format results
            retrieved_docs = []
            if results and len(results) > 0:
                for neighbor in results[0]:
                    retrieved_docs.append({
                        'datapoint_id': neighbor.id,
                        'distance': neighbor.distance,
                        'score': 1.0 - neighbor.distance  # Convert distance to similarity score
                    })
            
            return retrieved_docs
            
        except Exception as e:
            print(f"❌ Error querying vector search: {e}")
            # Fallback: return empty list
            return []
    
    def retrieve_sops(self, exception_type: str, 
                     driver_note: Optional[str] = None,
                     num_results: int = 3) -> Dict:
        """
        Retrieve relevant SOPs for a given exception type.
        
        Args:
            exception_type: Predicted exception type (e.g., "Access Issue")
            driver_note: Optional driver note for context
            num_results: Number of SOPs to retrieve
            
        Returns:
            Dictionary with retrieved SOPs and metadata
        """
        # Build query
        if driver_note:
            query = f"{exception_type} exception: {driver_note}"
        else:
            query = f"{exception_type} exception procedure"
        
        print(f"🔍 Querying for: {query}")
        
        # Generate query embedding
        query_embedding = self.generate_query_embedding(query)
        
        # Query vector search with exception type filter
        results = self.query_vector_search(
            query_embedding=query_embedding,
            num_neighbors=num_results,
            exception_type_filter=exception_type
        )
        
        # Format response
        return {
            'exception_type': exception_type,
            'query': query,
            'num_results': len(results),
            'sops': results
        }
    
    def get_sop_content(self, datapoint_id: str) -> Optional[str]:
        """
        Retrieve the full SOP content for a datapoint ID.
        
        In a production system, you'd store SOP content in a database
        and retrieve it using the datapoint_id. For now, this is a placeholder.
        
        Args:
            datapoint_id: Datapoint ID from vector search results
            
        Returns:
            SOP content or None
        """
        # Map datapoint IDs to SOP files
        # In production, use a database or storage system
        sop_file_map = {
            'sop_access_issue': 'sops/access_issue.txt',
            'sop_address_invalid': 'sops/address_invalid.txt',
            'sop_customer_not_home': 'sops/customer_not_home.txt',
            'sop_driver_issue': 'sops/driver_issue.txt',
            'sop_hub_delay': 'sops/hub_delay.txt',
            'sop_misroute': 'sops/misroute.txt',
            'sop_package_damage': 'sops/package_damage.txt',
            'sop_system_error': 'sops/system_error.txt',
            'sop_unknown': 'sops/unknown.txt',
            'sop_weather_delay': 'sops/weather_delay.txt',
        }
        
        # Extract exception type from datapoint_id
        exception_type = datapoint_id.replace('sop_', '').replace('_', ' ')
        sop_file = sop_file_map.get(datapoint_id)
        
        if sop_file and os.path.exists(sop_file):
            with open(sop_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def format_sop_response(self, retrieval_result: Dict) -> str:
        """
        Format retrieved SOPs into a readable response.
        
        Args:
            retrieval_result: Result from retrieve_sops()
            
        Returns:
            Formatted string with SOP information
        """
        response = f"Retrieved SOPs for: {retrieval_result['exception_type']}\n"
        response += "=" * 60 + "\n\n"
        
        for i, sop in enumerate(retrieval_result['sops'], 1):
            datapoint_id = sop['datapoint_id']
            score = sop['score']
            
            # Get SOP content
            content = self.get_sop_content(datapoint_id)
            
            response += f"SOP {i} (Score: {score:.4f})\n"
            response += f"ID: {datapoint_id}\n"
            if content:
                # Include first few lines of content
                lines = content.split('\n')[:10]
                response += "Content preview:\n"
                response += '\n'.join(lines)
                response += "\n...\n"
            response += "\n" + "-" * 60 + "\n\n"
        
        return response


def retrieve_sops_for_exception(exception_type: str,
                                driver_note: Optional[str] = None,
                                project_id: Optional[str] = None,
                                region: Optional[str] = None,
                                index_id: Optional[str] = None,
                                endpoint_id: Optional[str] = None,
                                deployed_index_id: Optional[str] = None) -> Dict:
    """
    Convenience function to retrieve SOPs for an exception.
    
    Args:
        exception_type: Predicted exception type
        driver_note: Optional driver note
        project_id: GCP Project ID (or from env)
        region: GCP Region (or from env)
        index_id: Index ID (or from env)
        endpoint_id: Endpoint ID (or from env)
        deployed_index_id: Deployed Index ID (or from env)
        
    Returns:
        Dictionary with retrieval results
    """
    # Get from environment if not provided
    project_id = project_id or os.getenv('GCP_PROJECT_ID')
    region = region or os.getenv('GCP_REGION', 'us-central1')
    index_id = index_id or os.getenv('VERTEX_AI_INDEX_ID')
    endpoint_id = endpoint_id or os.getenv('VERTEX_AI_ENDPOINT_ID')
    deployed_index_id = deployed_index_id or os.getenv('VERTEX_AI_DEPLOYED_INDEX_ID')
    
    if not all([project_id, index_id, endpoint_id, deployed_index_id]):
        raise ValueError("Missing required GCP configuration. Provide as arguments or set environment variables.")
    
    # Initialize agent
    agent = SOPRetrievalAgent(
        project_id=project_id,
        region=region,
        index_id=index_id,
        endpoint_id=endpoint_id,
        deployed_index_id=deployed_index_id
    )
    
    # Retrieve SOPs
    return agent.retrieve_sops(
        exception_type=exception_type,
        driver_note=driver_note
    )


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Retrieve SOPs using RAG")
    parser.add_argument("--exception-type", required=True, help="Exception type to retrieve SOPs for")
    parser.add_argument("--driver-note", help="Optional driver note for context")
    parser.add_argument("--project-id", help="GCP Project ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument("--index-id", help="Vertex AI Index ID")
    parser.add_argument("--endpoint-id", help="Vertex AI Index Endpoint ID")
    parser.add_argument("--deployed-index-id", help="Deployed Index ID")
    
    args = parser.parse_args()
    
    result = retrieve_sops_for_exception(
        exception_type=args.exception_type,
        driver_note=args.driver_note,
        project_id=args.project_id,
        region=args.region,
        index_id=args.index_id,
        endpoint_id=args.endpoint_id,
        deployed_index_id=args.deployed_index_id
    )
    
    print("\n" + "="*60)
    print("SOP Retrieval Results")
    print("="*60)
    print(f"Exception Type: {result['exception_type']}")
    print(f"Query: {result['query']}")
    print(f"Results Found: {result['num_results']}")
    print("\nRetrieved SOPs:")
    for i, sop in enumerate(result['sops'], 1):
        print(f"  {i}. {sop['datapoint_id']} (score: {sop['score']:.4f})")


