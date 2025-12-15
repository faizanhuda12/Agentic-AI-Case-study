"""
Workflow Orchestrator API

This API orchestrates the multi-agent workflow:
1. Agent 1 (Classification) - Classifies the delivery exception
2. Agent 2 (SOP Retrieval) - Retrieves relevant SOP from Vector Search
3. Agent 3 (Decision) - Makes operational decision using LLM
4. Agent 4 (Action Executor) - Logs to Google Sheets, sends notifications

The frontend calls this single endpoint which coordinates all agents.
"""

import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="FedEx Exception Workflow API",
    description="Orchestrates multi-agent workflow for exception handling",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent URLs from environment (with defaults for deployed services)
AGENT1_URL = os.getenv("AGENT1_URL", "https://fedex-api-q55v7lau5a-uc.a.run.app")
AGENT2_URL = os.getenv("AGENT2_URL", "https://fedex-sop-retrieval-214205443062.us-central1.run.app")
AGENT3_URL = os.getenv("AGENT3_URL", "https://fedex-decision-214205443062.us-central1.run.app")
AGENT4_URL = os.getenv("AGENT4_URL", "https://fedex-action-executor-q55v7lau5a-uc.a.run.app")


# Request/Response models
class WorkflowRequest(BaseModel):
    """Request model for the full workflow."""
    driver_note: str = Field(..., description="Driver note text")
    gps_deviation_km: float = Field(..., description="GPS deviation in km")
    weather_condition: str = Field(..., description="Weather condition")
    attempts: int = Field(..., description="Number of delivery attempts")
    hub_delay_minutes: int = Field(..., description="Hub delay in minutes")
    package_scan_result: str = Field(..., description="Package scan result")
    time_of_day: str = Field(..., description="Time of day")


class Agent1Response(BaseModel):
    """Response from Agent 1 (Classification)."""
    predicted_label: str
    confidence: float
    top_predictions: List[Dict[str, Any]]


class SOPResult(BaseModel):
    """Individual SOP result."""
    datapoint_id: str
    score: float
    content: Optional[str] = None


class Agent2Response(BaseModel):
    """Response from Agent 2 (SOP Retrieval)."""
    exception_type: str
    query: str
    num_results: int
    sops: List[SOPResult]
    status: str


class DecisionOutput(BaseModel):
    """Decision output from Agent 3."""
    recommended_action: str
    driver_instruction: str
    customer_message: str
    requires_escalation: bool
    confidence: float
    reasoning_summary: str


class ActionOutput(BaseModel):
    """Action output from Agent 4."""
    sheet_updated: bool
    email_simulated: bool
    escalated: bool
    timestamp: str


class WorkflowResponse(BaseModel):
    """Combined workflow response."""
    # Agent 1 results
    predicted_label: str
    confidence: float
    top_predictions: List[Dict[str, Any]]
    
    # Agent 2 results
    sop_retrieved: bool
    sop_content: Optional[str] = None
    sop_score: Optional[float] = None
    sop_id: Optional[str] = None
    
    # Agent 3 results
    decision: Optional[DecisionOutput] = None
    
    # Agent 4 results
    action: Optional[ActionOutput] = None
    
    # Workflow metadata
    agents_executed: List[str]
    status: str


# Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FedEx Exception Workflow Orchestrator",
        "version": "2.0.0",
        "agents": {
            "agent1": AGENT1_URL,
            "agent2": AGENT2_URL,
            "agent3": AGENT3_URL,
            "agent4": AGENT4_URL
        },
        "endpoints": {
            "/workflow": "POST - Run full agent workflow",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check - also checks agent connectivity."""
    agent1_healthy = False
    agent2_healthy = False
    agent3_healthy = False
    agent4_healthy = False
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{AGENT1_URL}/health")
            agent1_healthy = resp.status_code == 200
        except:
            pass
        
        try:
            resp = await client.get(f"{AGENT2_URL}/health")
            agent2_healthy = resp.status_code == 200
        except:
            pass
        
        try:
            resp = await client.get(f"{AGENT3_URL}/health")
            agent3_healthy = resp.status_code == 200
        except:
            pass
        
        try:
            resp = await client.get(f"{AGENT4_URL}/health")
            agent4_healthy = resp.status_code == 200
        except:
            pass
    
    all_healthy = agent1_healthy and agent2_healthy and agent3_healthy and agent4_healthy
    return {
        "status": "healthy" if all_healthy else "degraded",
        "agents": {
            "agent1_classification": agent1_healthy,
            "agent2_sop_retrieval": agent2_healthy,
            "agent3_decision": agent3_healthy,
            "agent4_action": agent4_healthy
        }
    }


@app.post("/workflow", response_model=WorkflowResponse)
async def run_workflow(data: WorkflowRequest):
    """
    Run the full agent workflow:
    1. Agent 1: Classify the exception
    2. Agent 2: Retrieve relevant SOP based on classification
    3. Agent 3: Make operational decision using LLM
    4. Agent 4: Execute actions (log to sheets, send notifications)
    
    Returns combined results from all agents.
    """
    agents_executed = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # ============================================================
        # AGENT 1: Classification
        # ============================================================
        print("Calling Agent 1 (Classification)...")
        
        agent1_payload = {
            "driver_note": data.driver_note,
            "gps_deviation_km": data.gps_deviation_km,
            "weather_condition": data.weather_condition,
            "attempts": data.attempts,
            "hub_delay_minutes": data.hub_delay_minutes,
            "package_scan_result": data.package_scan_result,
            "time_of_day": data.time_of_day,
            "top_k": 3
        }
        
        try:
            resp1 = await client.post(
                f"{AGENT1_URL}/predict",
                json=agent1_payload
            )
            
            if resp1.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Agent 1 (Classification) failed: {resp1.text}"
                )
            
            agent1_result = resp1.json()
            agents_executed.append("agent1_classification")
            print(f"   Classified as: {agent1_result['predicted_label']} ({agent1_result['confidence']:.4f})")
            
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Agent 1 (Classification) unavailable: {str(e)}"
            )
        
        # ============================================================
        # AGENT 2: SOP Retrieval
        # ============================================================
        print("Calling Agent 2 (SOP Retrieval)...")
        
        agent2_payload = {
            "exception_type": agent1_result["predicted_label"],
            "driver_note": data.driver_note,
            "num_results": 1
        }
        
        sop_retrieved = False
        sop_content = None
        sop_score = None
        sop_id = None
        
        try:
            resp2 = await client.post(
                f"{AGENT2_URL}/retrieve",
                json=agent2_payload
            )
            
            if resp2.status_code == 200:
                agent2_result = resp2.json()
                agents_executed.append("agent2_sop_retrieval")
                
                if agent2_result.get("sops") and len(agent2_result["sops"]) > 0:
                    sop = agent2_result["sops"][0]
                    sop_retrieved = True
                    sop_content = sop.get("content")
                    sop_score = sop.get("score")
                    sop_id = sop.get("datapoint_id")
                    print(f"   Retrieved SOP: {sop_id} (score: {sop_score:.4f})")
                else:
                    print("   No SOP found for this exception type")
            else:
                print(f"   Agent 2 returned status {resp2.status_code}")
                
        except httpx.RequestError as e:
            print(f"   Agent 2 unavailable: {str(e)}")
            # Don't fail the whole workflow if Agent 2 fails
        
        # ============================================================
        # AGENT 3: Decision Making (LLM)
        # ============================================================
        print("Calling Agent 3 (Decision)...")
        
        decision = None
        decision_dict = None
        
        agent3_payload = {
            "predicted_label": agent1_result["predicted_label"],
            "confidence": agent1_result["confidence"],
            "top_predictions": agent1_result.get("top_predictions", []),
            "driver_note": data.driver_note,
            "gps_deviation_km": data.gps_deviation_km,
            "weather_condition": data.weather_condition,
            "attempts": data.attempts,
            "hub_delay_minutes": data.hub_delay_minutes,
            "package_scan_result": data.package_scan_result,
            "time_of_day": data.time_of_day,
            "sop_content": sop_content
        }
        
        try:
            resp3 = await client.post(
                f"{AGENT3_URL}/decide",
                json=agent3_payload,
                timeout=90.0  # LLM can take longer
            )
            
            if resp3.status_code == 200:
                agent3_result = resp3.json()
                agents_executed.append("agent3_decision")
                
                decision_dict = agent3_result.get("decision", {})
                decision = DecisionOutput(
                    recommended_action=decision_dict.get("recommended_action", ""),
                    driver_instruction=decision_dict.get("driver_instruction", ""),
                    customer_message=decision_dict.get("customer_message", ""),
                    requires_escalation=decision_dict.get("requires_escalation", False),
                    confidence=decision_dict.get("confidence", 0.0),
                    reasoning_summary=decision_dict.get("reasoning_summary", "")
                )
                print(f"   Decision made: {decision.recommended_action[:60]}...")
                print(f"      Escalation required: {decision.requires_escalation}")
            else:
                print(f"   Agent 3 returned status {resp3.status_code}")
                
        except httpx.RequestError as e:
            print(f"   Agent 3 unavailable: {str(e)}")
        except Exception as e:
            print(f"   Agent 3 error: {str(e)}")
        
        # ============================================================
        # AGENT 4: Action Executor (Google Sheets + Notifications)
        # ============================================================
        print("Calling Agent 4 (Action Executor)...")
        
        action = None
        
        agent4_payload = {
            # Input data
            "driver_note": data.driver_note,
            "gps_deviation_km": data.gps_deviation_km,
            "weather_condition": data.weather_condition,
            "attempts": data.attempts,
            "hub_delay_minutes": data.hub_delay_minutes,
            "package_scan_result": data.package_scan_result,
            "time_of_day": data.time_of_day,
            # Agent 1 results
            "predicted_label": agent1_result["predicted_label"],
            "confidence": agent1_result["confidence"],
            "top_predictions": agent1_result.get("top_predictions", []),
            # Agent 2 results
            "sop_retrieved": sop_retrieved,
            "sop_id": sop_id,
            # Agent 3 results
            "decision": decision_dict
        }
        
        try:
            resp4 = await client.post(
                f"{AGENT4_URL}/execute",
                json=agent4_payload,
                timeout=30.0
            )
            
            if resp4.status_code == 200:
                agent4_result = resp4.json()
                agents_executed.append("agent4_action")
                
                action = ActionOutput(
                    sheet_updated=agent4_result.get("sheet_updated", False),
                    email_simulated=agent4_result.get("email_simulated", False),
                    escalated=agent4_result.get("escalated", False),
                    timestamp=agent4_result.get("timestamp", "")
                )
                print(f"   Actions executed:")
                print(f"      Sheet Updated: {action.sheet_updated}")
                print(f"      Email Simulated: {action.email_simulated}")
                print(f"      Escalated: {action.escalated}")
            else:
                print(f"   Agent 4 returned status {resp4.status_code}")
                
        except httpx.RequestError as e:
            print(f"   Agent 4 unavailable: {str(e)}")
        except Exception as e:
            print(f"   Agent 4 error: {str(e)}")
        
        # ============================================================
        # Build Response
        # ============================================================
        return WorkflowResponse(
            # Agent 1 results
            predicted_label=agent1_result["predicted_label"],
            confidence=agent1_result["confidence"],
            top_predictions=agent1_result.get("top_predictions", []),
            
            # Agent 2 results
            sop_retrieved=sop_retrieved,
            sop_content=sop_content,
            sop_score=sop_score,
            sop_id=sop_id,
            
            # Agent 3 results
            decision=decision,
            
            # Agent 4 results
            action=action,
            
            # Metadata
            agents_executed=agents_executed,
            status="success"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
