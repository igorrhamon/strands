import time
import threading
import itertools
import sys
from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


class Spinner:
    def __init__(self, message="Loading...", delay=0.1):
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self.message = message

    def spin(self):
        while self.busy:
            sys.stdout.write(f'\r{self.message} {next(self.spinner)}')
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write(f'\r{" " * (len(self.message) + 2)}\r') # Clear the line
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.busy = False
        self.thread.join()
        sys.stdout.write('\r')


def main():
    http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
    agent = Agent(model=http_model)

    with Spinner("Agent processing..."):
        resp = agent("Explique como funciona o loop de agentes em Strands.")

    # AgentResult implements __str__ to return the last textual message
    print('Agent response:\n', str(resp))


if __name__ == "__main__":
    main()
