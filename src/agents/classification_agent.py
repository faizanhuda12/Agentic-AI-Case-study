"""
Classification Agent

This agent classifies exceptions by calling the FastAPI /predict endpoint.
"""

import requests
from typing import Dict, Any


class ClassificationAgent:
    """Agent that classifies exceptions using the FastAPI endpoint."""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """
        Initialize the Classification Agent.
        
        Args:
            api_url: Base URL of the FastAPI service
        """
        self.api_url = api_url
    
    def classify(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify exception by calling the FastAPI /predict endpoint.
        
        Args:
            state: Current agent state containing exception data
            
        Returns:
            Updated state with predicted_label and confidence
        """
        print("\n" + "="*60)
        print("🤖 Classification Agent: Classifying Exception")
        print("="*60)
        
        # Prepare request payload
        payload = {
            "driver_note": state["driver_note"],
            "gps_deviation_km": state["gps_deviation_km"],
            "weather_condition": state["weather_condition"],
            "attempts": state["attempts"],
            "hub_delay_minutes": state["hub_delay_minutes"],
            "package_scan_result": state["package_scan_result"],
            "time_of_day": state["time_of_day"]
        }
        
        try:
            # Make HTTP POST request
            response = requests.post(
                f"{self.api_url}/predict",
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Classification API returned status {response.status_code}: {response.text}")
            
            result = response.json()
            
            # Update state with classification results
            state["predicted_label"] = result["predicted_label"]
            state["confidence"] = result["confidence"]
            
            print(f"✅ Predicted Label: {result['predicted_label']}")
            print(f"   Confidence: {result['confidence']:.4f}")
            print(f"\nTop Predictions:")
            for i, pred in enumerate(result.get('top_predictions', [])[:3], 1):
                print(f"   {i}. {pred['label']}: {pred['confidence']:.4f}")
            
            return state
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling classification API: {e}")
            raise
        except Exception as e:
            print(f"❌ Error in classification: {e}")
            raise
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Make the agent callable for LangGraph."""
        return self.classify(state)


