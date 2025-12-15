"""
Google Sheets Operational Log Agent

Logs ALL exception handling data to Google Sheets - a comprehensive operational log
that captures every piece of information from all agents in the workflow.

=== SETUP INSTRUCTIONS ===

1. Create a Google Cloud Project (or use existing)
2. Enable Google Sheets API:
   - Go to: https://console.cloud.google.com/apis/library/sheets.googleapis.com
   - Click "Enable"

3. Create a Service Account:
   - Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
   - Click "Create Service Account"
   - Give it a name like "fedex-sheets-agent"
   - Click "Create and Continue"
   - Skip the optional steps, click "Done"

4. Create and Download Credentials:
   - Click on your new service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key" > JSON
   - Save the downloaded file as 'google_credentials.json' in the project root

5. Create a Google Sheet:
   - Go to https://docs.google.com/spreadsheets
   - Create a new spreadsheet (name it "FedEx Exception Log" or similar)
   - Copy the Sheet ID from the URL:
     https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit
   
6. Share the Sheet with the Service Account:
   - In Google Sheets, click "Share"
   - Add the service account email (looks like: your-name@your-project.iam.gserviceaccount.com)
   - Give it "Editor" access

7. Set Environment Variables:
   - GOOGLE_SHEET_ID=your_sheet_id_here
   - GOOGLE_SHEETS_CREDENTIALS_PATH=./google_credentials.json
   
   OR for Cloud Run (using secrets):
   - GOOGLE_SHEETS_CREDENTIALS_JSON={"type":"service_account",...}

=== COLUMNS LOGGED ===

This agent logs a comprehensive row with data from ALL agents:
- Input Data: All 7 input fields
- Agent 1 (Classification): Prediction, confidence, alternatives
- Agent 2 (SOP Retrieval): Whether SOP was found, which one
- Agent 3 (Decision): Full decision including action, messages, escalation
- Metadata: Timestamp, processing status
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import gspread
from google.oauth2.service_account import Credentials


class GoogleSheetsAgent:
    """
    Comprehensive Operational Log Agent for Google Sheets.
    
    Logs ALL data from the entire workflow - inputs and outputs from every agent.
    Uses append-only pattern (adds new rows, never edits existing).
    """
    
    # Complete column headers for operational log
    # Captures EVERYTHING from the workflow
    COLUMNS = [
        # Metadata
        "Timestamp",
        "Processing Status",
        
        # Input Data (what came into the system)
        "Driver Note",
        "GPS Deviation (km)",
        "Weather Condition",
        "Delivery Attempts",
        "Hub Delay (mins)",
        "Package Scan Result",
        "Time of Day",
        
        # Agent 1: Classification Results
        "Predicted Exception",
        "Classification Confidence",
        "2nd Best Prediction",
        "2nd Best Confidence",
        
        # Agent 2: SOP Retrieval Results
        "SOP Retrieved",
        "SOP ID",
        
        # Agent 3: Decision Results
        "Recommended Action",
        "Driver Instruction",
        "Customer Message",
        "Requires Escalation",
        "Decision Confidence",
        "Reasoning Summary"
    ]
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_json: Optional[str] = None,
        sheet_id: Optional[str] = None,
        worksheet_name: str = "Exception Log"
    ):
        """
        Initialize the Google Sheets Agent.
        
        Args:
            credentials_path: Path to service account JSON file
            credentials_json: Raw JSON string of credentials (for cloud deployment)
            sheet_id: Google Sheet ID from URL
            worksheet_name: Name of worksheet to use/create
        """
        self.credentials_path = credentials_path or os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        self.credentials_json = credentials_json or os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        self.sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID")
        self.worksheet_name = worksheet_name
        
        self.client = None
        self.sheet = None
        self.worksheet = None
        self._initialized = False
        
        # Print setup status
        print("\n" + "="*60)
        print("📊 Google Sheets Agent: Initializing")
        print("="*60)
        
        if not self.sheet_id:
            print("⚠️  GOOGLE_SHEET_ID not set")
            print("   → Get it from your sheet URL:")
            print("     https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit")
        
        has_creds = bool(self.credentials_path and os.path.exists(self.credentials_path)) or bool(self.credentials_json)
        if not has_creds:
            print("⚠️  No credentials found")
            print("   → Set GOOGLE_SHEETS_CREDENTIALS_PATH or GOOGLE_SHEETS_CREDENTIALS_JSON")
        
        # Initialize if configured
        if self.sheet_id and has_creds:
            try:
                self._initialize_client()
                self._initialized = True
                print(f"✅ Connected to Google Sheets!")
                print(f"   Sheet: {self.sheet.title}")
                print(f"   Worksheet: {self.worksheet_name}")
            except Exception as e:
                print(f"❌ Failed to connect: {e}")
                print("   Agent will run in SIMULATION mode")
        else:
            print("\n📋 Running in SIMULATION mode (will print logs instead of writing)")
    
    def _initialize_client(self):
        """Initialize gspread client and open the sheet."""
        scopes = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Load credentials
        if self.credentials_path and os.path.exists(self.credentials_path):
            creds = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=scopes
            )
        elif self.credentials_json:
            creds_dict = json.loads(self.credentials_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            raise ValueError("No valid credentials found")
        
        # Authorize and open sheet
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(self.sheet_id)
        
        # Get or create worksheet
        try:
            self.worksheet = self.sheet.worksheet(self.worksheet_name)
            # Check if headers exist
            first_row = self.worksheet.row_values(1)
            if not first_row:
                self.worksheet.append_row(self.COLUMNS)
        except gspread.WorksheetNotFound:
            self.worksheet = self.sheet.add_worksheet(
                title=self.worksheet_name,
                rows=1000,
                cols=len(self.COLUMNS)
            )
            self.worksheet.append_row(self.COLUMNS)
            print(f"   Created new worksheet: {self.worksheet_name}")
    
    def _safe_str(self, value: Any, max_length: int = 500) -> str:
        """Safely convert value to string with length limit."""
        if value is None:
            return ""
        s = str(value)
        if len(s) > max_length:
            return s[:max_length] + "..."
        return s
    
    def _build_row_from_state(self, state: Dict[str, Any]) -> List[str]:
        """
        Build a complete row from the workflow state.
        Extracts ALL data from all agents.
        """
        # Timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Determine processing status
        decision = state.get("decision_output", {})
        if decision.get("requires_escalation"):
            status = "ESCALATED"
        elif decision.get("recommended_action"):
            status = "PROCESSED"
        elif state.get("predicted_label"):
            status = "CLASSIFIED ONLY"
        else:
            status = "ERROR"
        
        # Get top predictions for 2nd best
        top_predictions = state.get("top_predictions", [])
        second_pred = ""
        second_conf = ""
        if len(top_predictions) >= 2:
            second_pred = top_predictions[1].get("label", "")
            second_conf = f"{top_predictions[1].get('confidence', 0):.4f}"
        
        # Build row matching COLUMNS order exactly
        row = [
            # Metadata
            timestamp,
            status,
            
            # Input Data
            self._safe_str(state.get("driver_note", "")),
            self._safe_str(state.get("gps_deviation_km", "")),
            self._safe_str(state.get("weather_condition", "")),
            self._safe_str(state.get("attempts", "")),
            self._safe_str(state.get("hub_delay_minutes", "")),
            self._safe_str(state.get("package_scan_result", "")),
            self._safe_str(state.get("time_of_day", "")),
            
            # Agent 1: Classification
            self._safe_str(state.get("predicted_label", "")),
            f"{state.get('confidence', 0):.4f}" if state.get("confidence") else "",
            second_pred,
            second_conf,
            
            # Agent 2: SOP Retrieval
            "Yes" if state.get("sop_content") else "No",
            self._safe_str(state.get("sop_metadata", {}).get("id", "")),
            
            # Agent 3: Decision
            self._safe_str(decision.get("recommended_action", "")),
            self._safe_str(decision.get("driver_instruction", "")),
            self._safe_str(decision.get("customer_message", "")),
            "Yes" if decision.get("requires_escalation") else "No",
            f"{decision.get('confidence', 0):.2f}" if decision.get("confidence") else "",
            self._safe_str(decision.get("reasoning_summary", ""))
        ]
        
        return row
    
    def log_to_sheet(self, state: Dict[str, Any]) -> bool:
        """
        Log the complete workflow state to Google Sheets.
        
        Returns:
            True if successful (or simulated), False on error
        """
        row = self._build_row_from_state(state)
        
        if not self._initialized:
            # Simulation mode - print what would be logged
            print("\n📋 [SIMULATION] Would log to Google Sheets:")
            print("-" * 50)
            for col, val in zip(self.COLUMNS, row):
                display_val = val[:60] + "..." if len(val) > 60 else val
                print(f"   {col}: {display_val}")
            print("-" * 50)
            return True
        
        try:
            self.worksheet.append_row(row, value_input_option='RAW')
            print(f"✅ Logged to Google Sheets successfully")
            return True
        except Exception as e:
            print(f"❌ Error logging to sheet: {e}")
            return False
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent: log complete workflow results to Google Sheets.
        
        This is called at the END of the workflow to log everything.
        """
        print("\n" + "="*60)
        print("📊 Google Sheets Agent: Logging Complete Workflow")
        print("="*60)
        
        success = self.log_to_sheet(state)
        
        # Update state with logging result
        state["sheet_updated"] = success
        state["sheet_log_timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        return state
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Make the agent callable for LangGraph."""
        return self.execute(state)


def create_google_sheets_agent(
    credentials_path: Optional[str] = None,
    credentials_json: Optional[str] = None,
    sheet_id: Optional[str] = None,
    worksheet_name: str = "Exception Log"
) -> GoogleSheetsAgent:
    """Factory function to create Google Sheets Agent."""
    return GoogleSheetsAgent(
        credentials_path=credentials_path,
        credentials_json=credentials_json,
        sheet_id=sheet_id,
        worksheet_name=worksheet_name
    )


# Test the agent
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 Testing Google Sheets Agent (Simulation Mode)")
    print("="*70)
    
    agent = GoogleSheetsAgent()
    
    # Complete mock state with data from ALL agents
    mock_state = {
        # Input data
        "driver_note": "Customer not available, tried doorbell twice. Dog barking inside.",
        "gps_deviation_km": 0.5,
        "weather_condition": "Clear",
        "attempts": 2,
        "hub_delay_minutes": 15,
        "package_scan_result": "OK",
        "time_of_day": "Afternoon",
        
        # Agent 1: Classification output
        "predicted_label": "Customer Not Home",
        "confidence": 0.9456,
        "top_predictions": [
            {"label": "Customer Not Home", "confidence": 0.9456},
            {"label": "Access Issue", "confidence": 0.0312},
            {"label": "Address Invalid", "confidence": 0.0098}
        ],
        
        # Agent 2: SOP Retrieval output
        "sop_content": "STANDARD OPERATING PROCEDURE – CUSTOMER NOT HOME...",
        "sop_metadata": {"id": "customer_not_home"},
        
        # Agent 3: Decision output
        "decision_output": {
            "recommended_action": "Leave delivery notice and schedule re-attempt for tomorrow morning",
            "driver_instruction": "Place door tag, note attempt in system, continue route",
            "customer_message": "We attempted delivery but you weren't available. We'll try again tomorrow between 9 AM - 12 PM.",
            "requires_escalation": False,
            "confidence": 0.92,
            "reasoning_summary": "Standard CNH case, 2nd attempt. Customer likely at work during afternoon delivery."
        }
    }
    
    result = agent(mock_state)
    
    print("\n" + "="*70)
    print(f"✅ Test Complete - Sheet Updated: {result['sheet_updated']}")
    print("="*70)
