"""
Action Executor Agent

This agent executes real operational actions based on the decision from Agent 3.
Actions include:
1. Send notification emails (simulated for POC)
2. Update Google Sheets operational log (direct integration via gspread)
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

# Import the Google Sheets agent for direct integration
from .google_sheets_agent import GoogleSheetsAgent


class ActionExecutorAgent:
    """
    Agent that executes operational actions.
    
    - Logs ALL data to Google Sheets (comprehensive operational log)
    - Email sending is simulated for POC (prints to console)
    """
    
    def __init__(
        self,
        customer_email: Optional[str] = None,
        dispatcher_email: Optional[str] = None,
        sheet_credentials_path: Optional[str] = None,
        sheet_credentials_json: Optional[str] = None,
        sheet_id: Optional[str] = None
    ):
        """
        Initialize the Action Executor Agent.
        
        Args:
            customer_email: Customer email for notifications (simulated)
            dispatcher_email: Dispatcher email for escalations (simulated)
            sheet_credentials_path: Path to Google service account JSON
            sheet_credentials_json: Raw JSON credentials (for cloud)
            sheet_id: Google Sheet ID from URL
        """
        self.customer_email = customer_email or os.getenv("CUSTOMER_EMAIL", "customer@example.com")
        self.dispatcher_email = dispatcher_email or os.getenv("DISPATCHER_EMAIL", "dispatcher@example.com")
        
        # Initialize Google Sheets agent for direct integration
        self.sheets_agent = GoogleSheetsAgent(
            credentials_path=sheet_credentials_path,
            credentials_json=sheet_credentials_json,
            sheet_id=sheet_id
        )
        
        print(f"\nInitialized Action Executor Agent")
        print(f"   Customer Email: {self.customer_email}")
        print(f"   Dispatcher Email: {self.dispatcher_email}")
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send email (simulated for POC - prints to console).
        
        In production, integrate with:
        - SendGrid, AWS SES, or similar email service
        - Or use smtplib with SMTP credentials
        """
        print(f"\n[SIMULATED EMAIL]")
        print(f"   To: {to}")
        print(f"   Subject: {subject}")
        print(f"   Body: {body[:200]}..." if len(body) > 200 else f"   Body: {body}")
        return True
    
    def execute_actions(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute operational actions based on decision_output.
        
        Actions:
        1. Send email notification (simulated)
        2. Log everything to Google Sheets (real or simulated based on config)
        
        Args:
            state: Current agent state with decision_output
            
        Returns:
            Updated state with executed_action
        """
        print("\n" + "="*60)
        print("Action Executor Agent: Executing Actions")
        print("="*60)
        
        # Get decision output
        decision_output = state.get("decision_output", {})
        if not decision_output:
            print("No decision_output found. Using defaults.")
        
        # Parse decision
        recommended_action = decision_output.get("recommended_action", "No action determined")
        customer_message = decision_output.get("customer_message", "")
        requires_escalation = decision_output.get("requires_escalation", False)
        exception_type = state.get("predicted_label", "Unknown")
        
        # Get current timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Track execution results
        email_sent = False
        sheet_updated = False
        
        # ============================================
        # ACTION 1: Send Email Notification (Simulated)
        # ============================================
        if customer_message or requires_escalation:
            print("\nSending email notification...")
            
            if requires_escalation:
                # Escalation email to dispatcher
                recipient = self.dispatcher_email
                subject = f"ESCALATION: {exception_type} Exception"
                body = f"""
ESCALATION REQUIRED

Exception Type: {exception_type}
Confidence: {state.get('confidence', 0):.2%}
Action Recommended: {recommended_action}

Driver Note: {state.get('driver_note', 'N/A')}

Reasoning: {decision_output.get('reasoning_summary', 'N/A')}

Please review and take appropriate action immediately.
"""
            else:
                # Customer notification
                recipient = self.customer_email
                subject = f"Delivery Update: {exception_type}"
                body = customer_message
            
            email_sent = self.send_email(to=recipient, subject=subject, body=body)
            print(f"   {'Success' if email_sent else 'Failed'} Email sent to {recipient}")
        else:
            print("\nNo email required (no customer message and no escalation)")
        
        # ============================================
        # ACTION 2: Log to Google Sheets
        # ============================================
        print("\nLogging to Google Sheets...")
        sheet_updated = self.sheets_agent.log_to_sheet(state)
        
        # ============================================
        # Build Execution Summary
        # ============================================
        executed_action = {
            "email_sent": email_sent,
            "email_recipient": recipient if (customer_message or requires_escalation) else None,
            "sheet_updated": sheet_updated,
            "escalated": requires_escalation,
            "action_taken": recommended_action,
            "timestamp": timestamp,
            "exception_type": exception_type
        }
        
        # Add to state
        state["executed_action"] = executed_action
        
        print("\n" + "="*60)
        print("Action Execution Summary")
        print("="*60)
        print(f"   Email Sent: {email_sent}")
        print(f"   Sheet Updated: {sheet_updated}")
        print(f"   Escalated: {requires_escalation}")
        print(f"   Action: {recommended_action[:60]}...")
        
        return state
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Make the agent callable for LangGraph."""
        return self.execute_actions(state)


def create_action_executor_agent(
    customer_email: Optional[str] = None,
    dispatcher_email: Optional[str] = None,
    sheet_credentials_path: Optional[str] = None,
    sheet_credentials_json: Optional[str] = None,
    sheet_id: Optional[str] = None,
    # Legacy params (ignored, kept for backwards compatibility)
    mcp_server_url: Optional[str] = None
) -> ActionExecutorAgent:
    """
    Factory function to create Action Executor Agent.
    
    Args:
        customer_email: Customer email for notifications
        dispatcher_email: Dispatcher email for escalations
        sheet_credentials_path: Path to Google credentials JSON
        sheet_credentials_json: Raw JSON credentials string
        sheet_id: Google Sheet ID
        
    Returns:
        ActionExecutorAgent instance
    """
    return ActionExecutorAgent(
        customer_email=customer_email,
        dispatcher_email=dispatcher_email,
        sheet_credentials_path=sheet_credentials_path,
        sheet_credentials_json=sheet_credentials_json,
        sheet_id=sheet_id
    )
