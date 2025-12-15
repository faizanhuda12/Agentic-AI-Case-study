"""
FastAPI Application for FedEx Exception Classification

This API provides endpoints for predicting exception types from delivery data.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
from classification_model.inference_pipeline import initialize_classifier, run_inference

# Initialize FastAPI app
app = FastAPI(
    title="FedEx Exception Classification API",
    description="API for predicting delivery exception types using TensorFlow",
    version="1.0.0"
)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global flag to track if classifier is loaded
classifier_loaded = False

# Initialize classifier on startup
@app.on_event("startup")
async def startup_event():
    """Initialize the classifier when the API starts."""
    global classifier_loaded
    try:
        initialize_classifier()
        classifier_loaded = True
        print("Classifier initialized successfully!")
    except Exception as e:
        print(f"Warning: Classifier not loaded: {e}")
        print("API will start but classification endpoints will return errors.")
        classifier_loaded = False


# Request/Response models
class ExceptionRequest(BaseModel):
    """Request model for exception prediction."""
    driver_note: str = Field(..., description="Driver note text", example="customer gate locked, couldn't enter")
    gps_deviation_km: float = Field(..., description="GPS deviation in kilometers", example=7.2)
    weather_condition: str = Field(..., description="Weather condition", example="Clear")
    attempts: int = Field(..., description="Number of delivery attempts", example=2)
    hub_delay_minutes: int = Field(..., description="Hub delay in minutes", example=30)
    package_scan_result: str = Field(..., description="Package scan result", example="OK")
    time_of_day: str = Field(..., description="Time of day", example="Afternoon")
    top_k: Optional[int] = Field(3, description="Number of top predictions to return", ge=1, le=10)
    
    class Config:
        schema_extra = {
            "example": {
                "driver_note": "customer gate locked, couldn't enter",
                "gps_deviation_km": 7.2,
                "weather_condition": "Clear",
                "attempts": 2,
                "hub_delay_minutes": 30,
                "package_scan_result": "OK",
                "time_of_day": "Afternoon",
                "top_k": 3
            }
        }


class PredictionItem(BaseModel):
    """Individual prediction item."""
    label: str
    confidence: float


class ExceptionResponse(BaseModel):
    """Response model for exception prediction."""
    predicted_label: str
    confidence: float
    top_predictions: List[PredictionItem]


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "FedEx Exception Classification API",
        "version": "1.0.0",
        "endpoints": {
            "/predict": "POST - Predict exception type",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "API is running"
    }


@app.post("/predict", response_model=ExceptionResponse)
async def predict_exception(data: ExceptionRequest):
    """
    Predict exception type from delivery data.
    
    This endpoint takes delivery information and returns the predicted
    exception type along with confidence scores and top-k predictions.
    
    **Parameters:**
    - `driver_note`: Text note from the driver
    - `gps_deviation_km`: GPS deviation in kilometers
    - `weather_condition`: Weather condition (Clear, Rain, Snow, Storm)
    - `attempts`: Number of delivery attempts
    - `hub_delay_minutes`: Hub delay in minutes
    - `package_scan_result`: Package scan result (OK, UNREADABLE, DAMAGED)
    - `time_of_day`: Time of day (Morning, Afternoon, Evening)
    - `top_k`: Number of top predictions to return (default: 3)
    
    **Returns:**
    - `predicted_label`: The top predicted exception type
    - `confidence`: Confidence score for the prediction
    - `top_predictions`: List of top-k predictions with confidence scores
    """
    try:
        # Validate categorical inputs
        valid_weather = ["Clear", "Rain", "Snow", "Storm"]
        valid_scan = ["OK", "UNREADABLE", "DAMAGED"]
        valid_time = ["Morning", "Afternoon", "Evening"]
        
        if data.weather_condition not in valid_weather:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid weather_condition. Must be one of: {valid_weather}"
            )
        
        if data.package_scan_result not in valid_scan:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid package_scan_result. Must be one of: {valid_scan}"
            )
        
        if data.time_of_day not in valid_time:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time_of_day. Must be one of: {valid_time}"
            )
        
        # Run inference
        result = run_inference(
            driver_note=data.driver_note,
            gps_deviation_km=data.gps_deviation_km,
            weather_condition=data.weather_condition,
            attempts=data.attempts,
            hub_delay_minutes=data.hub_delay_minutes,
            package_scan_result=data.package_scan_result,
            time_of_day=data.time_of_day,
            top_k=data.top_k
        )
        
        # Format response
        top_predictions = [
            PredictionItem(label=pred['label'], confidence=pred['confidence'])
            for pred in result['top_predictions']
        ]
        
        return ExceptionResponse(
            predicted_label=result['predicted_label'],
            confidence=result['confidence'],
            top_predictions=top_predictions
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during prediction: {str(e)}"
        )


if __name__ == "__main__":
    # Run the API server
    uvicorn.run(app, host="0.0.0.0", port=8000)

