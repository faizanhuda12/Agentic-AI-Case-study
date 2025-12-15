"""
SOP Retrieval Agent

This agent retrieves relevant Standard Operating Procedures (SOPs) 
using Vertex AI Vector Search based on the predicted exception type.
"""

import os
from typing import Dict, Any, Optional
from rag_retrieval import SOPRetrievalAgent


class SOPRetrievalAgentWrapper:
    """Agent that retrieves relevant SOPs using Vertex AI Vector Search."""
    
    def __init__(self, project_id: str, region: str, index_id: str, 
                 endpoint_id: str, deployed_index_id: str):
        """
        Initialize the SOP Retrieval Agent.
        
        Args:
            project_id: GCP Project ID
            region: GCP Region
            index_id: Vertex AI Index ID
            endpoint_id: Vertex AI Index Endpoint ID
            deployed_index_id: Deployed Index ID
        """
        self.retrieval_agent = SOPRetrievalAgent(
            project_id=project_id,
            region=region,
            index_id=index_id,
            endpoint_id=endpoint_id,
            deployed_index_id=deployed_index_id
        )
    
    def retrieve_sop(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve relevant SOP based on predicted exception type.
        
        Args:
            state: Current agent state with predicted_label
            
        Returns:
            Updated state with sop_content and sop_metadata
        """
        print("\n" + "="*60)
        print("SOP Retrieval Agent: Retrieving Relevant SOP")
        print("="*60)
        
        predicted_label = state["predicted_label"]
        driver_note = state.get("driver_note", "")
        
        try:
            # Retrieve SOPs using RAG
            result = self.retrieval_agent.retrieve_sops(
                exception_type=predicted_label,
                driver_note=driver_note,
                num_results=1  # Get the most relevant SOP
            )
            
            if result["num_results"] == 0:
                print("No SOPs found for this exception type")
                state["sop_content"] = "No relevant SOP found."
                state["sop_metadata"] = {}
                return state
            
            # Get the top result
            top_sop = result["sops"][0]
            datapoint_id = top_sop["datapoint_id"]
            
            # Retrieve full SOP content
            sop_content = self.retrieval_agent.get_sop_content(datapoint_id)
            
            if not sop_content:
                sop_content = f"SOP for {predicted_label} (ID: {datapoint_id})"
            
            # Update state (set both sop_content and sop_text for compatibility)
            state["sop_content"] = sop_content
            state["sop_text"] = sop_content  # Alias for decision agent
            state["sop_metadata"] = {
                "datapoint_id": datapoint_id,
                "score": top_sop["score"],
                "exception_type": predicted_label
            }
            
            print(f"Retrieved SOP for: {predicted_label}")
            print(f"   Score: {top_sop['score']:.4f}")
            print(f"   Content length: {len(sop_content)} characters")
            print(f"\nSOP Preview (first 200 chars):")
            print(sop_content[:200] + "..." if len(sop_content) > 200 else sop_content)
            
            return state
            
        except Exception as e:
            print(f"Error retrieving SOP: {e}")
            state["sop_content"] = f"Error retrieving SOP: {str(e)}"
            state["sop_metadata"] = {}
            return state
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Make the agent callable for LangGraph."""
        return self.retrieve_sop(state)


def create_sop_retrieval_agent(
    project_id: Optional[str] = None,
    region: str = "us-central1",
    index_id: Optional[str] = None,
    endpoint_id: Optional[str] = None,
    deployed_index_id: Optional[str] = None
) -> Optional[SOPRetrievalAgentWrapper]:
    """
    Factory function to create SOP Retrieval Agent from environment or arguments.
    
    Args:
        project_id: GCP Project ID (or from env)
        region: GCP Region
        index_id: Vertex AI Index ID (or from env)
        endpoint_id: Vertex AI Endpoint ID (or from env)
        deployed_index_id: Deployed Index ID (or from env)
        
    Returns:
        SOPRetrievalAgentWrapper instance or None if config missing
    """
    # Get from environment if not provided
    project_id = project_id or os.getenv("GCP_PROJECT_ID")
    region = region or os.getenv("GCP_REGION", "us-central1")
    index_id = index_id or os.getenv("VERTEX_AI_INDEX_ID")
    endpoint_id = endpoint_id or os.getenv("VERTEX_AI_ENDPOINT_ID")
    deployed_index_id = deployed_index_id or os.getenv("VERTEX_AI_DEPLOYED_INDEX_ID")
    
    if not all([project_id, index_id, endpoint_id, deployed_index_id]):
        return None
    
    return SOPRetrievalAgentWrapper(
        project_id=project_id,
        region=region,
        index_id=index_id,
        endpoint_id=endpoint_id,
        deployed_index_id=deployed_index_id
    )

