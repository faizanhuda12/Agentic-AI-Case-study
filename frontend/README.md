# FedEx Exception Classifier - Frontend

React frontend for the FedEx Exception Classification System.

## Features

- Clean, modern UI with gradient design
- Form inputs for all classification parameters:
  - Driver note (text area)
  - GPS deviation (number)
  - Weather condition (dropdown)
  - Delivery attempts (number)
  - Hub delay (number)
  - Package scan result (dropdown)
  - Time of day (dropdown)
- Real-time classification results
- Confidence visualization
- Top predictions display
- Responsive design

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Make sure the FastAPI backend is running on `http://localhost:8000`

3. Start the development server:
```bash
npm start
```

The app will open at `http://localhost:3000`

## Configuration

The frontend is configured to proxy API requests to `http://localhost:8000` (see `package.json` proxy setting).

To change the API URL, update the fetch URL in `App.js` or set up environment variables.

## Build for Production

```bash
npm run build
```

This creates an optimized production build in the `build` folder.


