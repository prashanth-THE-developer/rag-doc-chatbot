# ---------- Stage 1: build the React frontend ----------
FROM node:22-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python backend ----------
FROM python:3.11-slim

# Hugging Face runs containers as a normal user, so we create one with writable folders
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/app/data /home/user/app/faiss_index && \
    chown -R user:user /home/user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

# Install the CPU-only PyTorch first (much smaller than the default download)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install the rest of our libraries
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model now, so the first request is not slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy our backend code and the built frontend
COPY --chown=user app ./app
COPY --chown=user --from=frontend-build /frontend/dist ./frontend/dist

# Hugging Face expects the app on port 7860
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]