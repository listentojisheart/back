FROM python:3.11-slim

# System deps for PDF/DOCX parsing + psycopg2 + build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Railway injects $PORT; default 8000 for local
ENV PORT=8000
EXPOSE 8000

# Startup: run migrations then launch uvicorn
# The start script is in a shell wrapper so we can log each step
CMD bash -c "\
    echo '>>> Running Alembic migrations...' && \
    alembic upgrade head && \
    echo '>>> Starting uvicorn on port ${PORT}...' && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2 \
"
