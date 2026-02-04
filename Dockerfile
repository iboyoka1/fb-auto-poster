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

# Use gunicorn with simple settings - no preload to avoid import issues
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --timeout 120 --log-level debug app:app
