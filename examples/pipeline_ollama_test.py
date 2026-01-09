#!/usr/bin/env python3
"""
Quick test of the Ollama pipeline - minimal example

This script tests just the basic flow without running the full pipeline.
Useful for verifying your Ollama setup is working.

Usage:
    export OLLAMA_HOST="http://localhost:11434"
    export OLLAMA_MODEL="llama3.1"
    python examples/pipeline_ollama_test.py
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.ollama_models import OllamaModels


async def test_ollama():
    """Test basic Ollama connectivity and response."""
    print("=" * 60)
    print("🧪 Testing Ollama Provider")
    print("=" * 60)
    
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model_id = os.environ.get("OLLAMA_MODEL", "llama3.1")
    
    print(f"Host: {host}")
    print(f"Model: {model_id}")
    print()
    
    try:
        # Initialize provider
        model = OllamaModels(host=host, model_id=model_id, timeout=30)
        print("✅ Provider initialized")
        
        # Test simple query
        test_prompt = "Say 'Hello from Ollama!' in one sentence."
        messages = [{"role": "user", "content": test_prompt}]
        
        print(f"\n📤 Sending test prompt: '{test_prompt}'")
        print("\n📥 Response:")
        print("-" * 60)
        
        response_text = ""
        async for event in model.stream(messages):
            if isinstance(event, dict):
                delta = event.get("contentBlockDelta", {}).get("delta", {})
                text = delta.get("text", "")
                if text:
                    response_text += text
                    print(text, end="", flush=True)
        
        print()
        print("-" * 60)
        
        if response_text:
            print("\n✅ Test successful! Ollama is responding correctly.")
            print(f"\n💡 You can now run the full pipeline:")
            print(f"   python examples/pipeline_ollama.py")
            return True
        else:
            print("\n❌ No response received from Ollama")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed: {type(e).__name__}: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check Ollama is running: ollama serve")
        print(f"   2. Verify model is pulled: ollama pull {model_id}")
        print("   3. Test manually: ollama run " + model_id + " 'hello'")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_ollama())
    sys.exit(0 if success else 1)
