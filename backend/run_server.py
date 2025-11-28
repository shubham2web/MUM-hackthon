"""
Simple server runner for Windows - avoids Hypercorn multiprocessing issues
"""
import asyncio
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Set Windows event loop policy before importing server
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import the app
from server import app

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Starting ATLAS Server")
    print("=" * 70)
    print("Server will be available at:")
    print("  • http://localhost:8000")
    print("  • http://127.0.0.1:8000")
    print("\nPress CTRL+C to stop the server")
    print("=" * 70)

    # Run using Quart's simple runner (works better on Windows)
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)
