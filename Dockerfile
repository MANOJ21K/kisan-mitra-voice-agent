# Kisan Mitra — container image for the Streamlit voice chat app.
FROM python:3.12-slim

# Keep Python lean and unbuffered for clean container logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# SARVAM_API_KEY is provided at runtime: docker run -e SARVAM_API_KEY=sk_...
# Shell form so $PORT (set by Render/Cloud Run) expands; defaults to 7860 locally.
EXPOSE 7860
CMD streamlit run streamlit_app.py --server.port ${PORT:-7860} --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
