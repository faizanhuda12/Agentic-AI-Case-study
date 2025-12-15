"""
Decision Agent API (Agent 3)

This API uses Gemini Pro LLM to analyze:
1. Classification result from Agent 1
2. SOP content from Agent 2
3. Delivery context

And produces a structured operational decision.
"""

import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn

from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate

# Initialize FastAPI app
app = FastAPI(
    title="FedEx Decision Agent API",
    description="Agent 3: Uses LLM to make operational decisions based on classification and SOP",
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

# Global LLM instance
llm = None
llm_initialized = False


@app.on_event("startup")
async def startup_event():
    """Initialize the LLM on startup."""
    global llm, llm_initialized
    
    project_id = os.getenv("GCP_PROJECT_ID")
    region = os.getenv("GCP_REGION", "us-central1")
    model_name = os.getenv("LLM_MODEL_NAME", "gemini-2.0-flash")
    
    if not project_id:
        print("GCP_PROJECT_ID not set. LLM will not be initialized.")
        return
    
    try:
        llm = ChatVertexAI(
            model_name=model_name,
            project=project_id,
            location=region,
            temperature=0.3
        )
        llm_initialized = True
        print(f"LLM initialized: {model_name}")
        print(f"   Project: {project_id}")
        print(f"   Region: {region}")
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        llm_initialized = False


# Request/Response models
class DecisionRequest(BaseModel):
    """Request model for decision making."""
    # Classification results (from Agent 1)
    predicted_label: str = Field(..., description="Exception type from Agent 1")
    confidence: float = Field(..., description="Classification confidence")
    top_predictions: Optional[List[Dict[str, Any]]] = Field(None, description="Top predictions from Agent 1")
    
    # Delivery context
    driver_note: str = Field(..., description="Driver's note")
    gps_deviation_km: float = Field(0.0, description="GPS deviation in km")
    weather_condition: str = Field("Clear", description="Weather condition")
    attempts: int = Field(1, description="Number of delivery attempts")
    hub_delay_minutes: int = Field(0, description="Hub delay in minutes")
    package_scan_result: str = Field("OK", description="Package scan result")
    time_of_day: str = Field("Morning", description="Time of day")
    
    # SOP content (from Agent 2)
    sop_content: Optional[str] = Field(None, description="SOP content from Agent 2")


class DecisionOutput(BaseModel):
    """Structured decision output."""
    recommended_action: str
    driver_instruction: str
    customer_message: str
    requires_escalation: bool
    confidence: float
    reasoning_summary: str


class DecisionResponse(BaseModel):
    """Response model for decision API."""
    decision: DecisionOutput
    status: str
    agent: str = "agent3_decision"


# Prompt template
DECISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are the FedEx Operational Decision Agent. Your role is to analyze delivery exceptions and determine the appropriate action based on:
1. The ML model's exception classification
2. The official Standard Operating Procedure (SOP)
3. The actual delivery context (driver notes, GPS, weather, etc.)

You must produce a structured JSON decision that guides operational actions."""),
    ("human", """Analyze the following delivery exception and produce a decision.

PREDICTION:
- Exception Type: {predicted_label}
- Confidence: {confidence_pct}

DELIVERY CONTEXT:
- Driver Note: {driver_note}
- GPS Deviation: {gps_deviation_km} km
- Weather Condition: {weather_condition}
- Delivery Attempts: {attempts}
- Hub Delay: {hub_delay_minutes} minutes
- Package Scan Result: {package_scan_result}
- Time of Day: {time_of_day}

STANDARD OPERATING PROCEDURE (SOP):
{sop_content}

Based on all of this information, produce a JSON decision with the following structure:
{{
  "recommended_action": "A clear, actionable recommendation",
  "driver_instruction": "Specific instructions for the driver",
  "customer_message": "Message to send to the customer via SMS/email",
  "requires_escalation": true or false,
  "confidence": 0.0 to 1.0 (your confidence in this decision),
  "reasoning_summary": "Brief explanation referencing the SOP and context"
}}

Consider:
- Does the SOP fit this scenario?
- How many attempts have been made? (More attempts may require escalation)
- Are there any safety concerns (weather, time of day)?
- What does the driver note indicate?

Return ONLY valid JSON, no additional text.""")
])


def parse_llm_response(content: str) -> Dict[str, Any]:
    """Parse LLM response, handling markdown code blocks."""
    content = content.strip()
    
    # Remove markdown code blocks
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    
    content = content.strip()
    return json.loads(content)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FedEx Decision Agent (Agent 3)",
        "version": "1.0.0",
        "llm_initialized": llm_initialized,
        "endpoints": {
            "/decide": "POST - Make operational decision",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "llm_initialized": llm_initialized,
        "model": os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash")
    }


@app.post("/decide", response_model=DecisionResponse)
async def make_decision(request: DecisionRequest):
    """
    Make an operational decision based on classification and SOP.
    
    This endpoint:
    1. Takes classification from Agent 1
    2. Takes SOP from Agent 2
    3. Uses Gemini LLM to reason and produce a decision
    """
    if not llm_initialized or llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM not initialized. Check API logs for errors."
        )
    
    try:
        # Build prompt
        sop_content = request.sop_content or "SOP not available. Use standard procedures."
        
        # Format confidence as percentage string (LangChain doesn't support format specifiers)
        confidence_pct = f"{request.confidence * 100:.2f}%"
        
        prompt = DECISION_PROMPT.format_messages(
            predicted_label=request.predicted_label,
            confidence_pct=confidence_pct,
            driver_note=request.driver_note,
            gps_deviation_km=request.gps_deviation_km,
            weather_condition=request.weather_condition,
            attempts=request.attempts,
            hub_delay_minutes=request.hub_delay_minutes,
            package_scan_result=request.package_scan_result,
            time_of_day=request.time_of_day,
            sop_content=sop_content
        )
        
        # Call LLM
        print(f"Calling LLM for decision on: {request.predicted_label}")
        response = llm.invoke(prompt)
        
        # Extract content
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON
        try:
            decision_dict = parse_llm_response(content)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"   Raw response: {content[:300]}...")
            # Fallback decision
            decision_dict = {
                "recommended_action": "Manual review required due to LLM parsing error",
                "driver_instruction": "Follow standard procedure for this exception type",
                "customer_message": "We encountered an issue with your delivery. We will contact you shortly.",
                "requires_escalation": True,
                "confidence": 0.3,
                "reasoning_summary": f"LLM response could not be parsed: {str(e)[:100]}"
            }
        
        # Ensure all required fields exist
        required_fields = {
            "recommended_action": "Manual review required",
            "driver_instruction": "Follow standard procedure",
            "customer_message": "We will contact you shortly.",
            "requires_escalation": False,
            "confidence": 0.5,
            "reasoning_summary": "Decision generated"
        }
        
        for field, default in required_fields.items():
            if field not in decision_dict:
                decision_dict[field] = default
        
        # Build response
        decision = DecisionOutput(
            recommended_action=decision_dict["recommended_action"],
            driver_instruction=decision_dict["driver_instruction"],
            customer_message=decision_dict["customer_message"],
            requires_escalation=decision_dict["requires_escalation"],
            confidence=float(decision_dict["confidence"]),
            reasoning_summary=decision_dict["reasoning_summary"]
        )
        
        print(f"Decision generated:")
        print(f"   Action: {decision.recommended_action[:60]}...")
        print(f"   Escalation: {decision.requires_escalation}")
        
        return DecisionResponse(
            decision=decision,
            status="success"
        )
        
    except Exception as e:
        print(f"Error making decision: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error making decision: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)

