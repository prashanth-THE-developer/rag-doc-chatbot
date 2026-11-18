# ---------- Stage 1: build the React frontend ----------
FROM node:22-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: light Python backend ----------
FROM python:3.11-slim

# FAISS needs the OpenMP library, which the slim image may not include
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install our Python libraries (no PyTorch anymore)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy our backend code and the built frontend
COPY app ./app
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Folders the app writes to
RUN mkdir -p data faiss_index

# Render tells us which port to use in the PORT variable (default 10000)
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]