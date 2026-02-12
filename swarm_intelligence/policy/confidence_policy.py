from pydantic import BaseModel

class ConfidencePolicy(BaseModel):
    pass

class DefaultConfidencePolicy(ConfidencePolicy):
    pass
