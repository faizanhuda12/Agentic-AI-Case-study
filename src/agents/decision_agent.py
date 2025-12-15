"""
Decision Agent

This agent uses an LLM to reason over the exception classification,
SOP document, and delivery context to produce a structured decision
on what action should be taken.
"""

import json
import os
from typing import Dict, Any, Optional
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


class DecisionAgent:
    """Agent that produces operational decisions using LLM reasoning."""
    
    def __init__(self, 
                 project_id: Optional[str] = None,
                 region: str = "us-central1",
                 model_name: str = "gemini-pro"):
        """
        Initialize the Decision Agent.
        
        Args:
            project_id: GCP Project ID (or from env)
            region: GCP Region
            model_name: Vertex AI model name (e.g., "gemini-pro", "gemini-1.5-pro")
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.region = region or os.getenv("GCP_REGION", "us-central1")
        self.model_name = model_name
        
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be provided or set as environment variable")
        
        # Initialize LLM
        self.llm = ChatVertexAI(
            model_name=self.model_name,
            project=self.project_id,
            location=self.region,
            temperature=0.3  # Lower temperature for more consistent outputs
        )
        
        # JSON output parser
        self.json_parser = JsonOutputParser()
        
        # Build the prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are the FedEx Operational Decision Agent. Your role is to analyze delivery exceptions and determine the appropriate action based on:
1. The ML model's exception classification
2. The official Standard Operating Procedure (SOP)
3. The actual delivery context (driver notes, GPS, weather, etc.)

You must produce a structured JSON decision that guides operational actions."""),
            ("human", """Analyze the following delivery exception and produce a decision.

PREDICTION:
- Exception Type: {predicted_label}
- Confidence: {confidence}

DELIVERY CONTEXT:
- Driver Note: {driver_note}
- GPS Deviation: {gps_deviation_km} km
- Weather Condition: {weather_condition}
- Delivery Attempts: {attempts}
- Hub Delay: {hub_delay_minutes} minutes
- Package Scan Result: {package_scan_result}
- Time of Day: {time_of_day}

STANDARD OPERATING PROCEDURE (SOP):
{sop_text}

Based on all of this information, produce a JSON decision with the following structure:
{{
  "recommended_action": "A clear, actionable recommendation (e.g., 'Schedule re-delivery for tomorrow between 10AM-1PM and send access code request to customer')",
  "driver_instruction": "Specific instructions for the driver (e.g., 'Do not leave the package. On next attempt, try alternate entrance and use the access code if provided')",
  "customer_message": "Message to send to the customer via SMS/email (e.g., 'We attempted to deliver your package but could not access your building. Please reply with your gate or buzzer code so we can re-attempt delivery tomorrow between 10AM-1PM')",
  "requires_escalation": true or false,
  "confidence": 0.0 to 1.0 (your confidence in this decision),
  "reasoning_summary": "A brief explanation of your decision, referencing the SOP, context, and why this action is appropriate"
}}

Consider:
- Does the SOP fit this scenario?
- How many attempts have been made? (More attempts may require escalation)
- Are there any safety concerns (weather, time of day)?
- What does the driver note indicate?
- Is escalation needed based on SOP guidelines?

Return ONLY valid JSON, no additional text.""")
        ])
    
    def build_prompt(self, state: Dict[str, Any]) -> str:
        """
        Build the prompt from state.
        
        Args:
            state: Current agent state
            
        Returns:
            Formatted prompt string
        """
        # Get SOP text (handle both sop_text and sop_content keys)
        sop_text = state.get("sop_text") or state.get("sop_content", "SOP not available")
        
        # Get top predictions if available
        top_predictions = state.get("top_predictions", [])
        top_predictions_text = ""
        if top_predictions:
            top_predictions_text = "\nTop Predictions:\n"
            for i, pred in enumerate(top_predictions[:3], 1):
                if isinstance(pred, dict):
                    label = pred.get("label", "Unknown")
                    conf = pred.get("confidence", 0.0)
                else:
                    label = str(pred)
                    conf = 0.0
                top_predictions_text += f"  {i}. {label}: {conf:.4f}\n"
        
        # Format the prompt
        prompt = self.prompt_template.format_messages(
            predicted_label=state.get("predicted_label", "Unknown"),
            confidence=state.get("confidence", 0.0),
            driver_note=state.get("driver_note", "No driver note"),
            gps_deviation_km=state.get("gps_deviation_km", 0.0),
            weather_condition=state.get("weather_condition", "Unknown"),
            attempts=state.get("attempts", 0),
            hub_delay_minutes=state.get("hub_delay_minutes", 0),
            package_scan_result=state.get("package_scan_result", "Unknown"),
            time_of_day=state.get("time_of_day", "Unknown"),
            sop_text=sop_text
        )
        
        return prompt
    
    def make_decision(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an operational decision based on the state.
        
        Args:
            state: Current agent state with classification and SOP
            
        Returns:
            Updated state with decision_output
        """
        print("\n" + "="*60)
        print("🧠 Decision Agent: Analyzing and Making Decision")
        print("="*60)
        
        try:
            # Build prompt
            prompt = self.build_prompt(state)
            
            # Get LLM response
            print("🔄 Calling LLM for decision reasoning...")
            response = self.llm.invoke(prompt)
            
            # Extract content
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON from response
            # Sometimes LLM wraps JSON in markdown code blocks
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove closing ```
            content = content.strip()
            
            # Parse JSON
            try:
                decision_output = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON parsing error: {e}")
                print(f"   Raw response: {content[:200]}...")
                # Fallback: create a basic decision structure
                decision_output = {
                    "recommended_action": "Review exception manually",
                    "driver_instruction": "Follow standard procedure for this exception type",
                    "customer_message": "We encountered an issue with your delivery. We will contact you shortly.",
                    "requires_escalation": True,
                    "confidence": 0.5,
                    "reasoning_summary": f"LLM response could not be parsed. Error: {str(e)}"
                }
            
            # Validate required fields
            required_fields = [
                "recommended_action",
                "driver_instruction",
                "customer_message",
                "requires_escalation",
                "confidence",
                "reasoning_summary"
            ]
            
            for field in required_fields:
                if field not in decision_output:
                    decision_output[field] = "Not provided" if field != "requires_escalation" else False
                    if field == "confidence":
                        decision_output[field] = 0.5
            
            # Update state
            state["decision_output"] = decision_output
            
            print(f"✅ Decision Generated:")
            print(f"   Recommended Action: {decision_output['recommended_action'][:80]}...")
            print(f"   Requires Escalation: {decision_output['requires_escalation']}")
            print(f"   Confidence: {decision_output['confidence']:.4f}")
            print(f"   Reasoning: {decision_output['reasoning_summary'][:100]}...")
            
            return state
            
        except Exception as e:
            print(f"❌ Error in decision making: {e}")
            # Create fallback decision
            state["decision_output"] = {
                "recommended_action": "Manual review required",
                "driver_instruction": "Hold package and await further instructions",
                "customer_message": "We encountered an issue with your delivery. We will contact you shortly.",
                "requires_escalation": True,
                "confidence": 0.0,
                "reasoning_summary": f"Error occurred during decision generation: {str(e)}"
            }
            return state
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Make the agent callable for LangGraph."""
        return self.make_decision(state)


def create_decision_agent(
    project_id: Optional[str] = None,
    region: str = "us-central1",
    model_name: str = "gemini-pro"
) -> DecisionAgent:
    """
    Factory function to create Decision Agent from environment or arguments.
    
    Args:
        project_id: GCP Project ID (or from env)
        region: GCP Region
        model_name: Vertex AI model name
        
    Returns:
        DecisionAgent instance
    """
    return DecisionAgent(
        project_id=project_id,
        region=region,
        model_name=model_name
    )


