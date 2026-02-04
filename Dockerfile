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

# Use simple Python startup for faster health check response
# gunicorn can be slow to start, use Flask directly with threaded mode
CMD python -c "from app import app; import os; app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), threaded=True)"
