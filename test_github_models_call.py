#!/usr/bin/env python3
"""Quick diagnostic script to test GitHub Models API call."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.providers.github_models import GitHubModels


async def test_call():
    """Test a simple GitHub Models call with timeout."""
    print("1. Checking GITHUB_TOKEN...")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not set")
        return
    print(f"   Token found: {token[:10]}...")

    print("\n2. Initializing provider...")
    model = GitHubModels(
        endpoint="https://models.github.ai/inference",
        model_name="openai/gpt-5",
        timeout=10  # 10 second timeout
    )
    print(f"   Provider initialized: {model.model_name}")

    print("\n3. Making API call...")
    messages = [{"role": "user", "content": "Say 'test' in one word"}]
    
    try:
        print("   Streaming response...")
        async for ev in model.stream(messages, system_prompt="You are a helpful assistant"):
            print(f"   Event received: {str(ev)[:100]}...")
        print("   ✓ Call completed successfully")
    except Exception as e:
        print(f"   ✗ Call failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=== GitHub Models Provider Diagnostic ===\n")
    asyncio.run(test_call())
