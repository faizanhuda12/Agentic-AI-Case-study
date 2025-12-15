"""
Action Executor API (Agent 4)

This API executes operational actions:
1. Logs ALL workflow data to Google Sheets (comprehensive operational log)
2. Simulates email notifications (for POC)

Called by the Workflow Orchestrator after Agent 3 (Decision) completes.
"""

import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
import gspread
from google.oauth2.service_account import Credentials

# Initialize FastAPI app
app = FastAPI(
    title="FedEx Action Executor API",
    description="Agent 4: Executes actions (Google Sheets logging, notifications)",
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

# Global Google Sheets client
sheets_client = None
sheets_initialized = False
worksheet = None

# Column headers for operational log
COLUMNS = [
    "Timestamp",
    "Processing Status",
    "Driver Note",
    "GPS Deviation (km)",
    "Weather Condition",
    "Delivery Attempts",
    "Hub Delay (mins)",
    "Package Scan Result",
    "Time of Day",
    "Predicted Exception",
    "Classification Confidence",
    "2nd Best Prediction",
    "2nd Best Confidence",
    "SOP Retrieved",
    "SOP ID",
    "Recommended Action",
    "Driver Instruction",
    "Customer Message",
    "Requires Escalation",
    "Decision Confidence",
    "Reasoning Summary"
]


@app.on_event("startup")
async def startup_event():
    """Initialize Google Sheets connection on startup."""
    global sheets_client, sheets_initialized, worksheet
    
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    credentials_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
    worksheet_name = os.getenv("GOOGLE_SHEETS_WORKSHEET", "Exception Log")
    
    if not sheet_id:
        print("GOOGLE_SHEET_ID not set. Sheets logging will be simulated.")
        return
    
    try:
        scopes = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Load credentials from JSON string or file
        if credentials_json:
            creds_dict = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        elif credentials_path and os.path.exists(credentials_path):
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        else:
            print("No Google credentials found. Sheets logging will be simulated.")
            return
        
        # Authorize and open sheet
        sheets_client = gspread.authorize(creds)
        sheet = sheets_client.open_by_key(sheet_id)
        
        # Get or create worksheet
        try:
            worksheet = sheet.worksheet(worksheet_name)
            first_row = worksheet.row_values(1)
            if not first_row:
                worksheet.append_row(COLUMNS)
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(COLUMNS))
            worksheet.append_row(COLUMNS)
            print(f"   Created new worksheet: {worksheet_name}")
        
        sheets_initialized = True
        print(f"Google Sheets initialized")
        print(f"   Sheet: {sheet.title}")
        print(f"   Worksheet: {worksheet_name}")
        
    except Exception as e:
        print(f"Error initializing Google Sheets: {e}")
        sheets_initialized = False


# Request/Response models
class ActionRequest(BaseModel):
    """Request model for action execution."""
    # Input data
    driver_note: str = Field(..., description="Driver's note")
    gps_deviation_km: float = Field(0.0, description="GPS deviation in km")
    weather_condition: str = Field("Clear", description="Weather condition")
    attempts: int = Field(1, description="Number of delivery attempts")
    hub_delay_minutes: int = Field(0, description="Hub delay in minutes")
    package_scan_result: str = Field("OK", description="Package scan result")
    time_of_day: str = Field("Morning", description="Time of day")
    
    # Classification results (from Agent 1)
    predicted_label: str = Field(..., description="Exception type")
    confidence: float = Field(..., description="Classification confidence")
    top_predictions: Optional[List[Dict[str, Any]]] = Field(None, description="Top predictions")
    
    # SOP results (from Agent 2)
    sop_retrieved: bool = Field(False, description="Whether SOP was retrieved")
    sop_id: Optional[str] = Field(None, description="SOP ID")
    
    # Decision results (from Agent 3)
    decision: Optional[Dict[str, Any]] = Field(None, description="Decision from Agent 3")


class ActionResponse(BaseModel):
    """Response model for action execution."""
    sheet_updated: bool
    email_simulated: bool
    escalated: bool
    timestamp: str
    status: str
    agent: str = "agent4_action"


def safe_str(value: Any, max_length: int = 500) -> str:
    """Safely convert value to string with length limit."""
    if value is None:
        return ""
    s = str(value)
    return s[:max_length] + "..." if len(s) > max_length else s


def build_row(request: ActionRequest) -> List[str]:
    """Build a row from the request data."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    decision = request.decision or {}
    
    # Determine status
    if decision.get("requires_escalation"):
        status = "ESCALATED"
    elif decision.get("recommended_action"):
        status = "PROCESSED"
    elif request.predicted_label:
        status = "CLASSIFIED ONLY"
    else:
        status = "ERROR"
    
    # Get 2nd best prediction
    second_pred = ""
    second_conf = ""
    if request.top_predictions and len(request.top_predictions) >= 2:
        second_pred = request.top_predictions[1].get("label", "")
        second_conf = f"{request.top_predictions[1].get('confidence', 0):.4f}"
    
    return [
        timestamp,
        status,
        safe_str(request.driver_note),
        safe_str(request.gps_deviation_km),
        safe_str(request.weather_condition),
        safe_str(request.attempts),
        safe_str(request.hub_delay_minutes),
        safe_str(request.package_scan_result),
        safe_str(request.time_of_day),
        safe_str(request.predicted_label),
        f"{request.confidence:.4f}",
        second_pred,
        second_conf,
        "Yes" if request.sop_retrieved else "No",
        safe_str(request.sop_id),
        safe_str(decision.get("recommended_action", "")),
        safe_str(decision.get("driver_instruction", "")),
        safe_str(decision.get("customer_message", "")),
        "Yes" if decision.get("requires_escalation") else "No",
        f"{decision.get('confidence', 0):.2f}" if decision.get("confidence") else "",
        safe_str(decision.get("reasoning_summary", ""))
    ]


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FedEx Action Executor (Agent 4)",
        "version": "1.0.0",
        "sheets_initialized": sheets_initialized,
        "endpoints": {
            "/execute": "POST - Execute actions (log to sheets, send notifications)",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "sheets_initialized": sheets_initialized
    }


@app.post("/execute", response_model=ActionResponse)
async def execute_actions(request: ActionRequest):
    """
    Execute operational actions:
    1. Log to Google Sheets (comprehensive operational log)
    2. Simulate email notification
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    decision = request.decision or {}
    requires_escalation = decision.get("requires_escalation", False)
    
    # ============================================
    # ACTION 1: Log to Google Sheets
    # ============================================
    sheet_updated = False
    
    if sheets_initialized and worksheet:
        try:
            row = build_row(request)
            worksheet.append_row(row, value_input_option='RAW')
            sheet_updated = True
            print(f"Logged to Google Sheets: {request.predicted_label}")
        except Exception as e:
            print(f"Error logging to sheets: {e}")
    else:
        # Simulation mode
        print(f"[SIMULATED] Would log: {request.predicted_label} - {decision.get('recommended_action', 'N/A')[:50]}")
        sheet_updated = True  # Return true for simulation
    
    # ============================================
    # ACTION 2: Simulate Email
    # ============================================
    email_simulated = False
    customer_message = decision.get("customer_message", "")
    
    if customer_message or requires_escalation:
        if requires_escalation:
            print(f"[SIMULATED] Escalation email to dispatcher")
            print(f"   Subject: ESCALATION: {request.predicted_label}")
        else:
            print(f"[SIMULATED] Customer notification email")
            print(f"   Message: {customer_message[:100]}...")
        email_simulated = True
    
    return ActionResponse(
        sheet_updated=sheet_updated,
        email_simulated=email_simulated,
        escalated=requires_escalation,
        timestamp=timestamp,
        status="success"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)

