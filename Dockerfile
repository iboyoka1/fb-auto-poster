FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers are already installed in the base image

# Copy project files
COPY . .

# Explicitly copy static and templates (ensure they're included)
COPY static/ ./static/
COPY templates/ ./templates/

# Debug: List files to verify copy
RUN echo "=== Listing /app ===" && ls -la /app && echo "=== Listing /app/static ===" && ls -la /app/static || echo "No static folder" && echo "=== Listing /app/templates ===" && ls -la /app/templates || echo "No templates folder"

# Create necessary directories
RUN mkdir -p sessions logs media_library backups uploads

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV SERVER_HOST=0.0.0.0

# Expose port (Render uses PORT env var)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/api/health || exit 1

# Run the application with gunicorn for production
CMD gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 2 --timeout 120 app:app
