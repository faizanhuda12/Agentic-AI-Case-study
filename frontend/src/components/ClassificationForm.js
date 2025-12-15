import React, { useState } from 'react';
import './ClassificationForm.css';

const ClassificationForm = ({ onSubmit, loading, error }) => {
  const [formData, setFormData] = useState({
    driver_note: '',
    gps_deviation_km: '',
    weather_condition: 'Clear',
    attempts: '',
    hub_delay_minutes: '',
    package_scan_result: 'OK',
    time_of_day: 'Morning',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.driver_note.trim()) {
      alert('Please enter a driver note');
      return;
    }

    // Convert numeric fields
    const submitData = {
      ...formData,
      gps_deviation_km: parseFloat(formData.gps_deviation_km) || 0,
      attempts: parseInt(formData.attempts) || 1,
      hub_delay_minutes: parseInt(formData.hub_delay_minutes) || 0,
    };

    onSubmit(submitData);
  };

  return (
    <div className="form-container">
      <form onSubmit={handleSubmit} className="classification-form">
        <div className="form-section">
          <h2>Delivery Information</h2>
          
          <div className="form-group">
            <label htmlFor="driver_note">
              Driver Note <span className="required">*</span>
            </label>
            <textarea
              id="driver_note"
              name="driver_note"
              value={formData.driver_note}
              onChange={handleChange}
              placeholder="e.g., customer gate locked, couldn't enter"
              rows="3"
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="gps_deviation_km">
                GPS Deviation (km)
              </label>
              <input
                type="number"
                id="gps_deviation_km"
                name="gps_deviation_km"
                value={formData.gps_deviation_km}
                onChange={handleChange}
                placeholder="0.0"
                step="0.1"
                min="0"
              />
            </div>

            <div className="form-group">
              <label htmlFor="attempts">
                Delivery Attempts
              </label>
              <input
                type="number"
                id="attempts"
                name="attempts"
                value={formData.attempts}
                onChange={handleChange}
                placeholder="1"
                min="1"
                max="10"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="hub_delay_minutes">
                Hub Delay (minutes)
              </label>
              <input
                type="number"
                id="hub_delay_minutes"
                name="hub_delay_minutes"
                value={formData.hub_delay_minutes}
                onChange={handleChange}
                placeholder="0"
                min="0"
              />
            </div>

            <div className="form-group">
              <label htmlFor="weather_condition">
                Weather Condition
              </label>
              <select
                id="weather_condition"
                name="weather_condition"
                value={formData.weather_condition}
                onChange={handleChange}
              >
                <option value="Clear">Clear</option>
                <option value="Rain">Rain</option>
                <option value="Snow">Snow</option>
                <option value="Storm">Storm</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="package_scan_result">
                Package Scan Result
              </label>
              <select
                id="package_scan_result"
                name="package_scan_result"
                value={formData.package_scan_result}
                onChange={handleChange}
              >
                <option value="OK">OK</option>
                <option value="UNREADABLE">UNREADABLE</option>
                <option value="DAMAGED">DAMAGED</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="time_of_day">
                Time of Day
              </label>
              <select
                id="time_of_day"
                name="time_of_day"
                value={formData.time_of_day}
                onChange={handleChange}
              >
                <option value="Morning">Morning</option>
                <option value="Afternoon">Afternoon</option>
                <option value="Evening">Evening</option>
              </select>
            </div>
          </div>
        </div>

        {error && (
          <div className="error-message">
            <strong>Error:</strong> {error}
          </div>
        )}

        <div className="form-actions">
          <button 
            type="submit" 
            className="submit-button"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner"></span>
                Classifying...
              </>
            ) : (
              'Classify Exception'
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default ClassificationForm;


