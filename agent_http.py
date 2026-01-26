import itertools
import sys
import threading
import time

from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


def main():
    http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
    agent = Agent(model=http_model)

    done = False
    def spin():
        for c in itertools.cycle(['|', '/', '-', '\\']):
            if done:
                break
            sys.stdout.write(f'\r🎨 Calling the agent... {c}')
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\rAgent called!         \n')

    spinner_thread = threading.Thread(target=spin)
    spinner_thread.start()

    try:
        resp = agent("Explique como funciona o loop de agentes em Strands.")
        # AgentResult implements __str__ to return the last textual message
        print('Agent response:\n', str(resp))
    finally:
        done = True
        spinner_thread.join()


if __name__ == "__main__":
    main()
