"""
LangGraph Workflow for FedEx Exception Classification System

This module orchestrates the workflow using LangGraph with two agents:
1. Classification Agent - Calls FastAPI /predict endpoint
2. SOP Retrieval Agent - Queries Vertex AI Vector Search for relevant SOPs
"""

import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Import agents from separate modules
from agents.classification_agent import ClassificationAgent
from agents.sop_retrieval_agent import create_sop_retrieval_agent
from agents.decision_agent import create_decision_agent
from agents.action_executor_agent import create_action_executor_agent


# ============================================================================
# State Definition
# ============================================================================

class AgentState(TypedDict):
    """State shared between agents."""
    # Input data (from original exception event)
    driver_note: str
    gps_deviation_km: float
    weather_condition: str
    attempts: int
    hub_delay_minutes: int
    package_scan_result: str
    time_of_day: str
    
    # Classification Agent output (Agent 1)
    predicted_label: str
    confidence: float
    top_predictions: list  # Optional list of top-k predictions
    
    # SOP Retrieval Agent output (Agent 2)
    sop_content: str  # Full SOP text
    sop_text: str  # Alias for sop_content
    sop_metadata: dict
    
    # Decision Agent output (Agent 3)
    decision_output: dict  # Structured decision JSON
    
    # Workflow metadata
    api_url: str,
    "messages": Annotated[list, add_messages]


# ============================================================================
# Agents are imported from separate modules
# ============================================================================


# ============================================================================
# LangGraph Workflow
# ============================================================================

def create_exception_workflow(
    api_url: str = "http://localhost:8000",
    project_id: str = None,
    region: str = "us-central1",
    index_id: str = None,
    endpoint_id: str = None,
    deployed_index_id: str = None,
    llm_model_name: str = "gemini-pro",
    customer_email: str = None,
    dispatcher_email: str = None,
    sheet_id: str = None,
    sheet_credentials_path: str = None,
    sheet_credentials_json: str = None
) -> StateGraph:
    """
    Create the LangGraph workflow with Classification and SOP Retrieval agents.
    
    Args:
        api_url: FastAPI endpoint URL
        project_id: GCP Project ID (or from env)
        region: GCP Region
        index_id: Vertex AI Index ID (or from env)
        endpoint_id: Vertex AI Endpoint ID (or from env)
        deployed_index_id: Deployed Index ID (or from env)
        
    Returns:
        Configured StateGraph workflow
    """
    # Get from environment if not provided
    project_id = project_id or os.getenv("GCP_PROJECT_ID")
    region = region or os.getenv("GCP_REGION", "us-central1")
    index_id = index_id or os.getenv("VERTEX_AI_INDEX_ID")
    endpoint_id = endpoint_id or os.getenv("VERTEX_AI_ENDPOINT_ID")
    deployed_index_id = deployed_index_id or os.getenv("VERTEX_AI_DEPLOYED_INDEX_ID")
    
    # Initialize agents from separate modules
    classification_agent = ClassificationAgent(api_url=api_url)
    
    # Only initialize SOP agent if GCP config is available
    sop_agent = create_sop_retrieval_agent(
        project_id=project_id,
        region=region,
        index_id=index_id,
        endpoint_id=endpoint_id,
        deployed_index_id=deployed_index_id
    )
    
    if not sop_agent:
        print("⚠️  GCP configuration not found. SOP Retrieval Agent will be disabled.")
        print("   Set environment variables:")
        print("   - GCP_PROJECT_ID")
        print("   - VERTEX_AI_INDEX_ID")
        print("   - VERTEX_AI_ENDPOINT_ID")
        print("   - VERTEX_AI_DEPLOYED_INDEX_ID")
    
    # Initialize Decision Agent (requires GCP for LLM)
    decision_agent = None
    if project_id or os.getenv("GCP_PROJECT_ID"):
        try:
            decision_agent = create_decision_agent(
                project_id=project_id,
                region=region,
                model_name=llm_model_name
            )
        except Exception as e:
            print(f"⚠️  Could not initialize Decision Agent: {e}")
            print("   Decision Agent will be disabled.")
    else:
        print("⚠️  GCP_PROJECT_ID not found. Decision Agent will be disabled.")
        print("   Set GCP_PROJECT_ID environment variable to enable Decision Agent.")
    
    # Initialize Action Executor Agent (with Google Sheets integration)
    action_executor_agent = create_action_executor_agent(
        customer_email=customer_email,
        dispatcher_email=dispatcher_email,
        sheet_id=sheet_id,
        sheet_credentials_path=sheet_credentials_path,
        sheet_credentials_json=sheet_credentials_json
    )
    
    # Create workflow graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify", classification_agent)
    
    if sop_agent:
        workflow.add_node("retrieve_sop", sop_agent)
    
    if decision_agent:
        workflow.add_node("make_decision", decision_agent)
    
    workflow.add_node("execute_actions", action_executor_agent)
    
    # Define edges
    workflow.set_entry_point("classify")
    
    # Build workflow chain based on available agents
    current_node = "classify"
    
    if sop_agent:
        workflow.add_edge(current_node, "retrieve_sop")
        current_node = "retrieve_sop"
    
    if decision_agent:
        workflow.add_edge(current_node, "make_decision")
        current_node = "make_decision"
    
    # Always end with action executor
    workflow.add_edge(current_node, "execute_actions")
    workflow.add_edge("execute_actions", END)
    
    return workflow.compile()


# ============================================================================
# Convenience Functions
# ============================================================================

def run_exception_workflow(
    driver_note: str,
    gps_deviation_km: float,
    weather_condition: str,
    attempts: int,
    hub_delay_minutes: int,
    package_scan_result: str,
    time_of_day: str,
    api_url: str = "http://localhost:8000",
    project_id: str = None,
    region: str = "us-central1",
    index_id: str = None,
    endpoint_id: str = None,
    deployed_index_id: str = None,
    llm_model_name: str = "gemini-pro",
    customer_email: str = None,
    dispatcher_email: str = None,
    sheet_id: str = None,
    sheet_credentials_path: str = None,
    sheet_credentials_json: str = None
) -> dict:
    """
    Run the complete exception classification and SOP retrieval workflow.
    
    Args:
        driver_note: Driver note text
        gps_deviation_km: GPS deviation in kilometers
        weather_condition: Weather condition (Clear, Rain, Snow, Storm)
        attempts: Number of delivery attempts
        hub_delay_minutes: Hub delay in minutes
        package_scan_result: Package scan result (OK, UNREADABLE, DAMAGED)
        time_of_day: Time of day (Morning, Afternoon, Evening)
        api_url: FastAPI endpoint URL
        project_id: GCP Project ID
        region: GCP Region
        index_id: Vertex AI Index ID
        endpoint_id: Vertex AI Endpoint ID
        deployed_index_id: Deployed Index ID
        
    Returns:
        Final state dictionary with classification and SOP results
    """
    # Create workflow
    app = create_exception_workflow(
        api_url=api_url,
        project_id=project_id,
        region=region,
        index_id=index_id,
        endpoint_id=endpoint_id,
        deployed_index_id=deployed_index_id,
        llm_model_name=llm_model_name,
        customer_email=customer_email,
        dispatcher_email=dispatcher_email,
        sheet_id=sheet_id,
        sheet_credentials_path=sheet_credentials_path,
        sheet_credentials_json=sheet_credentials_json
    )
    
    # Initial state
    initial_state = {
        "driver_note": driver_note,
        "gps_deviation_km": gps_deviation_km,
        "weather_condition": weather_condition,
        "attempts": attempts,
        "hub_delay_minutes": hub_delay_minutes,
        "package_scan_result": package_scan_result,
        "time_of_day": time_of_day,
        "api_url": api_url,
        "messages": [],
        # Initialize optional fields
        "top_predictions": [],
        "sop_metadata": {}
    }
    
    # Run workflow
    print("\n" + "="*60)
    print("🚀 Starting Exception Classification Workflow")
    print("="*60)
    
    final_state = app.invoke(initial_state)
    
    print("\n" + "="*60)
    print("✅ Workflow Completed")
    print("="*60)
    print(f"\nFinal Results:")
    print(f"  Predicted Exception: {final_state.get('predicted_label', 'N/A')}")
    print(f"  Confidence: {final_state.get('confidence', 0):.4f}")
    if final_state.get('sop_content'):
        print(f"  SOP Retrieved: Yes ({len(final_state['sop_content'])} chars)")
    else:
        print(f"  SOP Retrieved: No")
    if final_state.get('decision_output'):
        decision = final_state['decision_output']
        print(f"  Decision Made: Yes")
        print(f"    Action: {decision.get('recommended_action', 'N/A')[:60]}...")
        print(f"    Escalation: {decision.get('requires_escalation', False)}")
    else:
        print(f"  Decision Made: No")
    if final_state.get('executed_action'):
        executed = final_state['executed_action']
        print(f"  Actions Executed: Yes")
        print(f"    Email Sent: {executed.get('email_sent', False)}")
        print(f"    Sheet Updated: {executed.get('sheet_updated', False)}")
        print(f"    Escalated: {executed.get('escalated', False)}")
    else:
        print(f"  Actions Executed: No")
    
    return final_state


if __name__ == "__main__":
    """Example usage of the LangGraph workflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run FedEx Exception Classification Workflow")
    parser.add_argument("--driver-note", required=True, help="Driver note text")
    parser.add_argument("--gps-deviation", type=float, required=True, help="GPS deviation in km")
    parser.add_argument("--weather", required=True, choices=["Clear", "Rain", "Snow", "Storm"])
    parser.add_argument("--attempts", type=int, required=True, help="Number of attempts")
    parser.add_argument("--hub-delay", type=int, required=True, help="Hub delay in minutes")
    parser.add_argument("--scan-result", required=True, choices=["OK", "UNREADABLE", "DAMAGED"])
    parser.add_argument("--time-of-day", required=True, choices=["Morning", "Afternoon", "Evening"])
    parser.add_argument("--api-url", default="http://localhost:8000", help="FastAPI URL")
    
    args = parser.parse_args()
    
    # Run workflow
    result = run_exception_workflow(
        driver_note=args.driver_note,
        gps_deviation_km=args.gps_deviation,
        weather_condition=args.weather,
        attempts=args.attempts,
        hub_delay_minutes=args.hub_delay,
        package_scan_result=args.scan_result,
        time_of_day=args.time_of_day,
        api_url=args.api_url
    )
    
    # Print results
    print("\n" + "="*60)
    print("Workflow Results")
    print("="*60)
    print(f"Predicted Label: {result.get('predicted_label')}")
    print(f"Confidence: {result.get('confidence', 0):.4f}")
    if result.get('sop_content'):
        print(f"\nRetrieved SOP:")
        print("-" * 60)
        print(result['sop_content'])
        print("-" * 60)

