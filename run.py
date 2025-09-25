#!/usr/bin/env python3
# run.py
# Simple script to start the Python backend

import os
import sys
from pathlib import Path

def main():
    print("🐍 Fixie AI Python Backend Starter")
    print("=" * 50)
    
    # Check if virtual environment exists
    venv_path = Path("venv")
    if not venv_path.exists():
        print("❌ Virtual environment not found!")
        print("Please run:")
        print("  python -m venv venv")
        print("  venv\\Scripts\\activate  # Windows")
        print("  source venv/bin/activate  # Mac/Linux")
        print("  pip install -r requirements.txt")
        return
    
    # Check if .env file exists
    env_path = Path(".env")
    if not env_path.exists():
        print("⚠️  .env file not found!")
        print("Creating .env template...")
        
        with open(".env", "w") as f:
            f.write("""# Environment variables for local testing
OPENAI_API_KEY=your-openai-api-key-here
FRESHDESK_DOMAIN=fixie-it.freshdesk.com
FRESHDESK_API_KEY=your-freshdesk-api-key-here
FRONTEND_URL=http://localhost:3000
""")
        
        print("✅ Created .env file. Please update with your actual API keys.")
        print("Then run: python main.py")
        return
    
    # Check environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key or openai_key == "your-openai-api-key-here":
        print("❌ OpenAI API key not set!")
        print("Please update OPENAI_API_KEY in your .env file")
        return
    
    print("✅ Environment configured")
    print("🚀 Starting FastAPI server...")
    print("📍 Server will run at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")
    print("🔍 Debug endpoint: http://localhost:8000/debug/conversations")
    print("\n💡 Update your frontend to use: http://localhost:8000/chat")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start the server
    os.system("python main.py")

if __name__ == "__main__":
    main()
