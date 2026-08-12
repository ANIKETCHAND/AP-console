import sys
import os

# Add root and backend to python path for Vercel Serverless Function entry point
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "backend"))

from backend.app import app

try:
    from mangum import Mangum
    handler = Mangum(app)
except Exception:
    handler = app
