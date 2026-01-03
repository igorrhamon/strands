import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path to import src module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.github_models import GitHubModels

try:
    from strands.agent import Agent
except Exception:
    Agent = None


def run_example():
    # Ensure token is present for real runs
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("⚠️  GITHUB_TOKEN not set — using mock example")
        token = "ghp_test"

    print(f"✅ Using token: {token[:20]}...")
    
    model = GitHubModels()
    print(f"✅ GitHubModels initialized")
    print(f"   Endpoint: {model.get_config()['endpoint']}")
    print(f"   Model: {model.get_config()['model_name']}")

    # Call provider directly using the stream interface
    print("\n📤 Example: Calling GitHub Models Provider\n")
    
    # For demo purposes, use mock client to avoid real network calls
    class MockResponse:
        def __init__(self):
            self.choices = [type('obj', (object,), {'role': 'assistant', 'message': 'Hello! 2+2 equals 4.'})]
    
    class MockClient:
        def __init__(self, endpoint, credential):
            pass
        def get_chat_response(self, model, messages, timeout):
            return MockResponse()
    
    # Use mock for demonstration (comment out to use real API)
    model._client_cls = MockClient
    
    async def demo():
        try:
            messages = [{"role": "user", "content": "Hello, what is 2+2?"}]
            print("Prompt:", messages[0]["content"])
            print("\nResponse:\n")
            async for ev in model.stream(messages, system_prompt="You are a helpful assistant."):
                if "contentBlockDelta" in ev:
                    text = ev["contentBlockDelta"]["delta"]["text"]
                    print(f"  {text}")
            print("\n✅ Done!")
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")

    asyncio.run(demo())


if __name__ == "__main__":
    run_example()
