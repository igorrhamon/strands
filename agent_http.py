from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


import sys
import time
import threading

def spinner():
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_spinner:
        sys.stdout.write(f"\r\033[36m{chars[i % len(chars)]}\033[0m Thinking...")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r\033[K")

def main():
    global stop_spinner
    http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
    agent = Agent(model=http_model)

    stop_spinner = False
    thread = threading.Thread(target=spinner)
    thread.start()

    try:
        resp = agent("Explique como funciona o loop de agentes em Strands.")
    finally:
        stop_spinner = True
        thread.join()

    # ANSI colors for delight
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"

    print(f"{BLUE}{BOLD}Agent response:{END}")
    print(str(resp))


if __name__ == "__main__":
    main()
