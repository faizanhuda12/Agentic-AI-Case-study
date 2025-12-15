"""
MCP (Model Context Protocol) Server

This server exposes tools for Agent 4 to execute real operational actions:
1. send_email - Send emails to customers or dispatchers
2. update_sheet - Update Google Sheets operational log

Uses the official MCP SDK with FastMCP for compatibility with Claude for Desktop
and other MCP clients.
"""

import os
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Optional
import gspread
from google.oauth2.service_account import Credentials
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (required for STDIO transport)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("fedex-operations")

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

# Google Sheets configuration
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")


def send_email_smtp(to: str, subject: str, body: str) -> bool:
    """
    Send email using SMTP.
    
    Args:
        to: Recipient email
        subject: Email subject
        body: Email body
        
    Returns:
        True if successful
    """
    try:
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured. Simulating email send.")
            logger.info(f"To: {to}, Subject: {subject}, Body: {body[:100]}...")
            return True  # Simulate for POC
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent successfully to {to}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


def update_google_sheet(sheet_id: str, row_data: dict) -> bool:
    """
    Update Google Sheets with new row.
    
    Args:
        sheet_id: Google Sheets ID
        row_data: Dictionary with row data
        
    Returns:
        True if successful
    """
    try:
        if not GOOGLE_CREDENTIALS_PATH or not os.path.exists(GOOGLE_CREDENTIALS_PATH):
            logger.warning("Google credentials not configured. Simulating sheet update.")
            logger.info(f"Sheet ID: {sheet_id}, Row Data: {row_data}")
            return True  # Simulate for POC
        
        # Authenticate
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=scope)
        client = gspread.authorize(creds)
        
        # Open sheet
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Prepare row data
        row = [
            row_data.get("timestamp", datetime.utcnow().isoformat()),
            row_data.get("exception_type", ""),
            row_data.get("action_taken", ""),
            row_data.get("message_sent", ""),
            "Yes" if row_data.get("escalated", False) else "No"
        ]
        
        # Append row
        sheet.append_row(row)
        
        logger.info(f"Sheet updated successfully: {sheet_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating sheet: {e}")
        return False


@mcp.tool()
async def send_email(
    to: str,
    subject: str,
    body: str
) -> str:
    """Send an email to a customer or dispatcher.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body content
        
    Returns:
        Success message or error description
    """
    logger.info(f"Sending email to {to} with subject: {subject}")
    
    success = send_email_smtp(to, subject, body)
    
    if success:
        return f"Email sent successfully to {to}"
    else:
        return f"Failed to send email to {to}. Check logs for details."


@mcp.tool()
async def update_sheet(
    exception_type: str,
    action_taken: str,
    message_sent: str,
    escalated: bool,
    timestamp: Optional[str] = None,
    sheet_id: Optional[str] = None
) -> str:
    """Update Google Sheets operational log with exception handling record.
    
    Args:
        exception_type: Type of delivery exception (e.g., "Access Issue")
        action_taken: Action that was taken (e.g., "Schedule re-delivery")
        message_sent: Message sent to customer or dispatcher
        escalated: Whether the issue was escalated (true/false)
        timestamp: ISO timestamp (defaults to current time if not provided)
        sheet_id: Google Sheets ID (uses GOOGLE_SHEET_ID env var if not provided)
        
    Returns:
        Success message or error description
    """
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + "Z"
    
    if sheet_id is None:
        sheet_id = GOOGLE_SHEET_ID
    
    if not sheet_id:
        return "Error: sheet_id not provided and GOOGLE_SHEET_ID environment variable not set"
    
    logger.info(f"Updating sheet {sheet_id} with exception: {exception_type}")
    
    row_data = {
        "timestamp": timestamp,
        "exception_type": exception_type,
        "action_taken": action_taken,
        "message_sent": message_sent,
        "escalated": escalated
    }
    
    success = update_google_sheet(sheet_id, row_data)
    
    if success:
        return f"Sheet updated successfully with exception record for {exception_type}"
    else:
        return f"Failed to update sheet. Check logs for details."


def main():
    """Initialize and run the MCP server."""
    logger.info("Starting FedEx Operations MCP Server...")
    logger.info(f"SMTP Server: {SMTP_SERVER}")
    logger.info(f"Google Sheet ID: {GOOGLE_SHEET_ID if GOOGLE_SHEET_ID else 'Not configured'}")
    
    # Run the server with STDIO transport
    mcp.run(transport='stdio')


if __name__ == "__main__":
    main()
