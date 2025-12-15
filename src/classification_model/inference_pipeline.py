"""
FedEx Exception Classification - Inference Pipeline

This module provides functions to preprocess input data and run inference
using the trained TensorFlow model.
"""

import numpy as np
import pickle
import re
import tensorflow as tf
import keras
from keras.models import load_model
from keras.utils import pad_sequences
from typing import Dict, List, Tuple, Optional
import os


class ExceptionClassifier:
    """Class to handle exception classification inference."""
    
    def __init__(self, model_path: str = None, preprocessing_path: str = None):
        """
        Initialize the classifier by loading the model and preprocessing objects.
        
        Args:
            model_path: Path to the saved TensorFlow model (default: in same directory)
            preprocessing_path: Path to the saved preprocessing objects (default: in same directory)
        """
        # Get directory of this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Set default paths if not provided
        if model_path is None:
            model_path = os.path.join(current_dir, 'fedex_exception_classifier_model.keras')
        if preprocessing_path is None:
            preprocessing_path = os.path.join(current_dir, 'preprocessing_objects.pkl')
        
        print("Loading model and preprocessing objects...")
        # Load the model (using native .keras format for Keras 3+ compatibility)
        self.model = load_model(model_path, compile=False)
        self.model_path = model_path
        self.preprocessing_path = preprocessing_path
        
        # Load preprocessing objects
        with open(preprocessing_path, 'rb') as f:
            preproc = pickle.load(f)
        
        self.tokenizer = preproc['tokenizer']
        self.scaler = preproc['scaler']
        self.label_encoder = preproc['label_encoder']
        self.categorical_encoders = preproc['categorical_encoders']
        self.max_length = preproc['max_length']
        
        print("Model and preprocessing objects loaded successfully!")
        print(f"Available classes: {list(self.label_encoder.classes_)}")
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text input.
        
        Args:
            text: Raw text input
            
        Returns:
            Cleaned text
        """
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def preprocess_text(self, text: str) -> np.ndarray:
        """
        Preprocess text: clean, tokenize, and pad.
        
        Args:
            text: Raw text input
            
        Returns:
            Padded sequence array ready for model input
        """
        # Clean text
        cleaned_text = self.clean_text(text)
        
        # Tokenize
        sequence = self.tokenizer.texts_to_sequences([cleaned_text])
        
        # Pad sequence
        padded = pad_sequences(sequence, maxlen=self.max_length, padding='post')
        
        return padded[0]
    
    def preprocess_numerical(self, gps_deviation_km: float, 
                            attempts: int, 
                            hub_delay_minutes: int) -> np.ndarray:
        """
        Preprocess numerical features: scale using StandardScaler.
        
        Args:
            gps_deviation_km: GPS deviation in kilometers
            attempts: Number of delivery attempts
            hub_delay_minutes: Hub delay in minutes
            
        Returns:
            Scaled numerical features array
        """
        # Create array
        numerical = np.array([[gps_deviation_km, attempts, hub_delay_minutes]])
        
        # Scale
        scaled = self.scaler.transform(numerical)
        
        return scaled[0]
    
    def preprocess_categorical(self, weather_condition: str,
                               package_scan_result: str,
                               time_of_day: str) -> np.ndarray:
        """
        Preprocess categorical features: encode using LabelEncoders.
        
        Args:
            weather_condition: Weather condition (Clear, Rain, Snow, Storm)
            package_scan_result: Package scan result (OK, UNREADABLE, DAMAGED)
            time_of_day: Time of day (Morning, Afternoon, Evening)
            
        Returns:
            Encoded categorical features array
        """
        # Encode each categorical feature
        weather_encoded = self.categorical_encoders['weather_condition'].transform([weather_condition])[0]
        scan_encoded = self.categorical_encoders['package_scan_result'].transform([package_scan_result])[0]
        time_encoded = self.categorical_encoders['time_of_day'].transform([time_of_day])[0]
        
        return np.array([weather_encoded, scan_encoded, time_encoded])
    
    def preprocess_all(self, driver_note: str,
                      gps_deviation_km: float,
                      weather_condition: str,
                      attempts: int,
                      hub_delay_minutes: int,
                      package_scan_result: str,
                      time_of_day: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess all input features.
        
        Args:
            driver_note: Driver note text
            gps_deviation_km: GPS deviation in kilometers
            weather_condition: Weather condition
            attempts: Number of delivery attempts
            hub_delay_minutes: Hub delay in minutes
            package_scan_result: Package scan result
            time_of_day: Time of day
            
        Returns:
            Tuple of (text_input, numerical_input) ready for model prediction
        """
        # Preprocess text
        text_input = self.preprocess_text(driver_note)
        text_input = text_input.reshape(1, -1)  # Add batch dimension
        
        # Preprocess numerical
        numerical_scaled = self.preprocess_numerical(gps_deviation_km, attempts, hub_delay_minutes)
        
        # Preprocess categorical
        categorical_encoded = self.preprocess_categorical(weather_condition, 
                                                         package_scan_result, 
                                                         time_of_day)
        
        # Combine numerical and categorical
        all_numerical = np.concatenate([numerical_scaled, categorical_encoded])
        all_numerical = all_numerical.reshape(1, -1)  # Add batch dimension
        
        return text_input, all_numerical
    
    def predict(self, driver_note: str,
                gps_deviation_km: float,
                weather_condition: str,
                attempts: int,
                hub_delay_minutes: int,
                package_scan_result: str,
                time_of_day: str,
                top_k: int = 3) -> Dict:
        """
        Run full inference pipeline: preprocess inputs and predict.
        
        Args:
            driver_note: Driver note text
            gps_deviation_km: GPS deviation in kilometers
            weather_condition: Weather condition (Clear, Rain, Snow, Storm)
            attempts: Number of delivery attempts
            hub_delay_minutes: Hub delay in minutes
            package_scan_result: Package scan result (OK, UNREADABLE, DAMAGED)
            time_of_day: Time of day (Morning, Afternoon, Evening)
            top_k: Number of top predictions to return
            
        Returns:
            Dictionary with predicted_label, confidence, and top_k predictions
        """
        # Preprocess all inputs
        text_input, numerical_input = self.preprocess_all(
            driver_note=driver_note,
            gps_deviation_km=gps_deviation_km,
            weather_condition=weather_condition,
            attempts=attempts,
            hub_delay_minutes=hub_delay_minutes,
            package_scan_result=package_scan_result,
            time_of_day=time_of_day
        )
        
        # Run prediction
        predictions = self.model.predict([text_input, numerical_input], verbose=0)
        probabilities = predictions[0]
        
        # Get top-k predictions
        top_indices = np.argsort(probabilities)[-top_k:][::-1]
        
        # Build results
        top_predictions = []
        for idx in top_indices:
            label = self.label_encoder.inverse_transform([idx])[0]
            confidence = float(probabilities[idx])
            top_predictions.append({
                'label': label,
                'confidence': confidence
            })
        
        # Get predicted label (top-1)
        predicted_idx = np.argmax(probabilities)
        predicted_label = self.label_encoder.inverse_transform([predicted_idx])[0]
        confidence = float(probabilities[predicted_idx])
        
        return {
            'predicted_label': predicted_label,
            'confidence': confidence,
            'top_predictions': top_predictions
        }


# Global classifier instance (will be initialized when module is imported)
classifier = None


def initialize_classifier(model_path: str = None, preprocessing_path: str = None):
    """Initialize the global classifier instance."""
    global classifier
    classifier = ExceptionClassifier(model_path, preprocessing_path)
    return classifier


def run_inference(driver_note: str,
                  gps_deviation_km: float,
                  weather_condition: str,
                  attempts: int,
                  hub_delay_minutes: int,
                  package_scan_result: str,
                  time_of_day: str,
                  top_k: int = 3) -> Dict:
    """
    Convenience function to run inference.
    
    Args:
        driver_note: Driver note text
        gps_deviation_km: GPS deviation in kilometers
        weather_condition: Weather condition
        attempts: Number of delivery attempts
        hub_delay_minutes: Hub delay in minutes
        package_scan_result: Package scan result
        time_of_day: Time of day
        top_k: Number of top predictions to return
        
    Returns:
        Dictionary with prediction results
    """
    if classifier is None:
        raise RuntimeError("Classifier not initialized. Call initialize_classifier() first.")
    
    return classifier.predict(
        driver_note=driver_note,
        gps_deviation_km=gps_deviation_km,
        weather_condition=weather_condition,
        attempts=attempts,
        hub_delay_minutes=hub_delay_minutes,
        package_scan_result=package_scan_result,
        time_of_day=time_of_day,
        top_k=top_k
    )


if __name__ == "__main__":
    # Example usage
    print("Initializing classifier...")
    initialize_classifier()
    
    # Example prediction
    result = run_inference(
        driver_note="customer gate locked, couldn't enter",
        gps_deviation_km=7.2,
        weather_condition="Clear",
        attempts=2,
        hub_delay_minutes=30,
        package_scan_result="OK",
        time_of_day="Afternoon"
    )
    
    print("\n" + "="*60)
    print("Prediction Results:")
    print("="*60)
    print(f"Predicted Label: {result['predicted_label']}")
    print(f"Confidence: {result['confidence']:.4f}")
    print(f"\nTop {len(result['top_predictions'])} Predictions:")
    for i, pred in enumerate(result['top_predictions'], 1):
        print(f"  {i}. {pred['label']}: {pred['confidence']:.4f}")

