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
    print("✅ GitHubModels initialized")
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
            pass  # Mock client for demo
        def get_chat_response(self, _model, _messages, _timeout):
            # Unused parameters required for API compatibility
            return MockResponse()
    
    # Use mock for demonstration (comment out to use real API)
    model._client_cls = MockClient  # type: ignore[assignment]
    
    async def demo():
        try:
            messages = [{"role": "user", "content": "Hello, what is 2+2?"}]
            print("Prompt:", messages[0]["content"])
            print("\nResponse:\n")
            async for ev in model.stream(messages, system_prompt="You are a helpful assistant."):  # type: ignore[arg-type]
                if "contentBlockDelta" in ev and isinstance(ev, dict):
                    cbd = ev.get("contentBlockDelta")
                    if isinstance(cbd, dict):
                        delta = cbd.get("delta")  # type: ignore[union-attr]
                        if isinstance(delta, dict):
                            text = delta.get("text")  # type: ignore[union-attr]
                            if isinstance(text, str):
                                print(f"  {text}")
            print("\n✅ Done!")
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")

    asyncio.run(demo())


if __name__ == "__main__":
    run_example()
