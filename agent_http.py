import httpx
import itertools
import sys
import time
from threading import Thread

from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


class Spinner:
    """A simple text-based spinner to show activity with Braille-like chars."""
    def __init__(self, message="Loading...", delay=0.1):
        # Braille-like chars for a more modern look (from PR #18)
        self.spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
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
            sys.stdout.write('\r' + ' ' * (len(self.message) + 4) + '\r')

def call_http_agent(prompt: str):
    print(f"\nPrompt: {prompt}")
    with Spinner("Agent is thinking..."):
        model = HTTPModel(MODEL_ENDPOINT)
        agent = Agent("http-demo-agent", model)
        response = agent.think(prompt)
    
    print(f"Agent Response: {response}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_prompt = " ".join(sys.argv[1:])
    else:
        user_prompt = "What is the capital of France?"
    
    call_http_agent(user_prompt)
