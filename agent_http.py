from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


import itertools
import sys
import threading
import time


def spinning_cursor():
    """A simple spinning cursor animation."""
    while True:
        for cursor in "|/-\\":
            yield cursor


def main():
    """Main function to run the agent with a loading animation."""
    http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
    agent = Agent(model=http_model)

    done = False
    spinner = spinning_cursor()

    def spin():
        """Function to run the spinner in a separate thread."""
        while not done:
            sys.stdout.write(f"\r🎨 Thinking... {next(spinner)}")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write("\r")
        sys.stdout.flush()

    spinner_thread = threading.Thread(target=spin)
    spinner_thread.start()

    try:
        resp = agent("Explique como funciona o loop de agentes em Strands.")
    finally:
        done = True
        spinner_thread.join()

    # AgentResult implements __str__ to return the last textual message
    print("--- 🎨 Agent Response ---")
    print(str(resp))
    print("--------------------------")


if __name__ == "__main__":
    main()
