"""WSGI entry point for gunicorn - optimized for Railway deployment"""
import os
import sys

# Set environment before imports
os.environ.setdefault('PYTHONUNBUFFERED', '1')

# Import the Flask app
from app import app

# This is the WSGI application gunicorn will use
application = app

if __name__ == '__main__':
    app.run()
