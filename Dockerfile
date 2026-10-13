# ----------------------------------------------------
# Stage 1: Build the Vite React Frontend
# ----------------------------------------------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/dashboard

COPY dashboard/package*.json ./
RUN npm install

COPY dashboard/ ./
RUN npm run build

# ----------------------------------------------------
# Stage 2: Python Backend & Production Container
# ----------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/agent \
    PORT=8080

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY agent/requirements.txt /app/agent/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/agent/requirements.txt

# Copy backend source code
COPY agent/ /app/agent/

# Copy compiled frontend static assets from builder stage
COPY --from=frontend-builder /app/dashboard/dist /app/dashboard/dist

WORKDIR /app/agent

EXPOSE 8080

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
