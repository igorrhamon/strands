from strands import Agent
from http_provider import HTTPModel


MODEL_ENDPOINT = "http://localhost:8000/generate"


def main():
    http_model = HTTPModel(endpoint_url=MODEL_ENDPOINT)
    agent = Agent(model=http_model)

    resp = agent("Explique como funciona o loop de agentes em Strands.")
    # AgentResult implements __str__ to return the last textual message
    print('Agent response:\n', str(resp))


if __name__ == "__main__":
    main()
