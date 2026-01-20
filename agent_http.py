import httpx
from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


def main():
    """
    Main function to run the agent.
    """
    try:
        http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
        agent = Agent(model=http_model)

        print("🎨 Sending prompt to the agent...")
        resp = agent("Explique como funciona o loop de agentes em Strands.")
        # AgentResult implements __str__ to return the last textual message
        print("\n✅ Agent response:\n", str(resp))

    except httpx.ConnectError:
        print("\n❌ Could not connect to the model endpoint.")
        print(f"   Please ensure the demo server is running on {MODEL_ENDPOINT}")
        print("   You can start it with: uvicorn server_fastapi:app --reload --port 8000")


if __name__ == "__main__":
    main()
