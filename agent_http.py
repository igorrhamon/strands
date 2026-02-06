import httpx
import itertools
import sys
import time
from threading import Thread

from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


class Spinner:
    """A simple text-based spinner to show activity."""
    def __init__(self, message="Loading...", delay=0.1):
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self.message = message
        self.thread = None

    def spin(self):
        while self.busy:
            sys.stdout.write(f"\r{self.message} {next(self.spinner)}")
            sys.stdout.flush()
            self.spinner_visible = True
            time.sleep(self.delay)

    def __enter__(self):
        self.busy = True
        self.thread = Thread(target=self.spin)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.busy = False
        if self.thread:
            self.thread.join()
        if self.spinner_visible:
            # Clear the entire line
            sys.stdout.write('\r' + ' ' * (len(self.message) + 2) + '\r')
            sys.stdout.flush()


def main():
    """Instantiates an agent and runs a prompt with a loading spinner."""
    try:
        http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
        agent = Agent(model=http_model)

        print("🎨 Sending prompt to agent...")
        with Spinner("Agent thinking..."):
            resp = agent("Explique como funciona o loop de agentes em Strands.")

        # AgentResult implements __str__ to return the last textual message
        print('\n✅ Agent response:\n', str(resp))

    except httpx.ConnectError:
        print("\n❌ Could not connect to the model endpoint.")
        print(f"   Please ensure the demo server is running on {MODEL_ENDPOINT}")
        print("   You can start it with: uvicorn server_fastapi:app --reload --port 8000")


if __name__ == "__main__":
    main()
