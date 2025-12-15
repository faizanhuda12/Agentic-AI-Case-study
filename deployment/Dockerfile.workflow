# Dockerfile for Workflow Orchestrator
# Chains Agent 1 → Agent 2 → Agent 3 → Agent 4

FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements/requirements_workflow.txt .
RUN pip install --no-cache-dir -r requirements_workflow.txt

# Copy application code
COPY src/workflow_api.py .

# Expose port
EXPOSE 8002

# Environment variables for agent URLs
ENV AGENT1_URL=https://fedex-api-q55v7lau5a-uc.a.run.app
ENV AGENT2_URL=https://fedex-sop-retrieval-214205443062.us-central1.run.app
ENV AGENT3_URL=https://fedex-decision-214205443062.us-central1.run.app
ENV AGENT4_URL=https://fedex-action-executor-q55v7lau5a-uc.a.run.app

# Run the API
CMD ["uvicorn", "workflow_api:app", "--host", "0.0.0.0", "--port", "8002"]

