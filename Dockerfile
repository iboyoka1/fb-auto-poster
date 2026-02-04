FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers are already installed in the base image

# Copy project files (static and templates are now tracked by git)
COPY . .

# Create necessary directories
RUN mkdir -p sessions logs media_library backups uploads

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV SERVER_HOST=0.0.0.0

# Expose port (Railway uses PORT env var)
EXPOSE ${PORT:-8080}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/health || exit 1

# Run with gunicorn - longer timeout for Railway
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 300 app:app
