"""
FastAPI Application for SOP Retrieval (Agent 2)

This API provides endpoints for retrieving relevant SOPs from Vertex AI Vector Search
based on the exception type predicted by Agent 1.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn

from google.cloud import aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel

# Initialize FastAPI app
app = FastAPI(
    title="FedEx SOP Retrieval API (Agent 2)",
    description="API for retrieving Standard Operating Procedures using Vertex AI Vector Search",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "agentic-ai-481216")
REGION = os.getenv("GCP_REGION", "us-central1")
INDEX_ENDPOINT_ID = os.getenv("VERTEX_AI_ENDPOINT_ID", "3201199516967501824")
DEPLOYED_INDEX_ID = os.getenv("VERTEX_AI_DEPLOYED_INDEX_ID", "fedex_sops_index_deployed")

# Global variables for initialized clients
embedding_model = None
index_endpoint = None

# SOP content mapping (loaded from files)
SOP_CONTENT = {}


def load_sop_files():
    """Load SOP files from the sops directory."""
    global SOP_CONTENT
    sops_dir = "sops"
    
    if not os.path.exists(sops_dir):
        print(f"SOPs directory not found: {sops_dir}")
        return
    
    for filename in os.listdir(sops_dir):
        if filename.endswith('.txt'):
            filepath = os.path.join(sops_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                sop_id = f"sop_{filename.replace('.txt', '')}"
                SOP_CONTENT[sop_id] = content
                print(f"   Loaded: {sop_id}")
    
    print(f"Loaded {len(SOP_CONTENT)} SOP files")


@app.on_event("startup")
async def startup_event():
    """Initialize clients when the API starts."""
    global embedding_model, index_endpoint
    
    print("="*60)
    print("Starting SOP Retrieval API (Agent 2)")
    print("="*60)
    print(f"   Project ID: {PROJECT_ID}")
    print(f"   Region: {REGION}")
    print(f"   Index Endpoint ID: {INDEX_ENDPOINT_ID}")
    print(f"   Deployed Index ID: {DEPLOYED_INDEX_ID}")
    print()
    
    try:
        # Initialize Vertex AI
        vertexai.init(project=PROJECT_ID, location=REGION)
        aiplatform.init(project=PROJECT_ID, location=REGION)
        
        # Initialize embedding model
        print("   Loading embedding model...")
        embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        print("   Embedding model loaded")
        
        # Initialize index endpoint
        print("   Connecting to Vector Search endpoint...")
        index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=f"projects/{PROJECT_ID}/locations/{REGION}/indexEndpoints/{INDEX_ENDPOINT_ID}"
        )
        print("   Connected to Vector Search endpoint")
        
        # Load SOP files
        print("   Loading SOP files...")
        load_sop_files()
        
        print()
        print("SOP Retrieval API initialized successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise


# Request/Response models
class SOPRetrievalRequest(BaseModel):
    """Request model for SOP retrieval."""
    exception_type: str = Field(..., description="Predicted exception type from Agent 1", example="Access Issue")
    driver_note: Optional[str] = Field(None, description="Optional driver note for context", example="customer gate locked")
    num_results: Optional[int] = Field(1, description="Number of SOPs to retrieve", ge=1, le=5)
    confidence: Optional[float] = Field(None, description="Confidence score from Agent 1")


class SOPResult(BaseModel):
    """Individual SOP result."""
    datapoint_id: str
    score: float
    content: Optional[str] = None


class SOPRetrievalResponse(BaseModel):
    """Response model for SOP retrieval."""
    exception_type: str
    query: str
    num_results: int
    sops: List[SOPResult]
    status: str


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "FedEx SOP Retrieval API (Agent 2)",
        "version": "1.0.0",
        "description": "Retrieves Standard Operating Procedures using Vertex AI Vector Search",
        "endpoints": {
            "/retrieve": "POST - Retrieve relevant SOPs for an exception type",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "SOP Retrieval API is running",
        "vector_search_connected": index_endpoint is not None,
        "embedding_model_loaded": embedding_model is not None,
        "sops_loaded": len(SOP_CONTENT)
    }


@app.post("/retrieve", response_model=SOPRetrievalResponse)
async def retrieve_sops(data: SOPRetrievalRequest):
    """
    Retrieve relevant SOPs based on exception type.
    
    This endpoint:
    1. Takes the exception type from Agent 1's prediction
    2. Generates an embedding for the query
    3. Queries Vertex AI Vector Search for similar SOPs
    4. Returns the matched SOPs with their content
    """
    global embedding_model, index_endpoint
    
    if not embedding_model or not index_endpoint:
        raise HTTPException(
            status_code=503,
            detail="Service not fully initialized. Vector Search or embedding model not available."
        )
    
    try:
        # Build query
        if data.driver_note:
            query = f"{data.exception_type} exception: {data.driver_note}"
        else:
            query = f"{data.exception_type} exception procedure"
        
        print(f"Query: {query}")
        
        # Generate query embedding
        embeddings = embedding_model.get_embeddings([query])
        query_embedding = embeddings[0].values
        
        print(f"   Generated embedding (dim: {len(query_embedding)})")
        
        # Query Vector Search
        results = index_endpoint.find_neighbors(
            deployed_index_id=DEPLOYED_INDEX_ID,
            queries=[query_embedding],
            num_neighbors=data.num_results
        )
        
        # Process results
        sops = []
        if results and len(results) > 0:
            for neighbor in results[0]:
                datapoint_id = neighbor.id
                distance = neighbor.distance
                score = 1.0 - distance  # Convert distance to similarity
                
                # Get SOP content
                content = SOP_CONTENT.get(datapoint_id)
                
                sops.append(SOPResult(
                    datapoint_id=datapoint_id,
                    score=score,
                    content=content
                ))
                
                print(f"   Found: {datapoint_id} (score: {score:.4f})")
        
        return SOPRetrievalResponse(
            exception_type=data.exception_type,
            query=query,
            num_results=len(sops),
            sops=sops,
            status="success"
        )
        
    except Exception as e:
        print(f"Error during retrieval: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during SOP retrieval: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

