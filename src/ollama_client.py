"""
Ollama LLM client for Strands.

Provides integration with locally-running Ollama for LLM capabilities.
"""

import httpx
import logging
import os
import asyncio
from typing import Optional
import json

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with Ollama LLM."""
    
    def __init__(self, base_url: str | None = None, model: str | None = None):
        # Resolve base_url: explicit param > OLLAMA_URL env > OLLAMA_HOST env > default localhost
        env_url = os.getenv("OLLAMA_URL")
        env_host = os.getenv("OLLAMA_HOST")
        resolved = base_url or env_url or env_host or "http://localhost:11434"
        # If env_host provided like '0.0.0.0:11434' or 'ollama:11434', ensure scheme
        if resolved and not resolved.startswith("http"):
            resolved = f"http://{resolved}"
        self.base_url = resolved
        # Resolve model: explicit param > OLLAMA_MODEL env > default 'mistral'
        env_model = os.getenv("OLLAMA_MODEL")
        self.model = model or env_model or "mistral"
        # Configurable timeout/retries via env
        timeout_val = float(os.getenv("OLLAMA_TIMEOUT", "60"))
        self._retries = max(1, int(os.getenv("OLLAMA_RETRIES", "3")))
        self.client = httpx.AsyncClient(timeout=timeout_val)
        
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Generate text using Ollama.
        
        Args:
            prompt: The input prompt
            system: Optional system message
            temperature: Sampling temperature (0-1)
            stream: Whether to stream the response
            
        Returns:
            Generated text
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": stream
        }
        
        if system:
            payload["system"] = system
            
        # Try with retries/backoff on connection errors
        last_exc = None
        for attempt in range(1, self._retries + 1):
            try:
                response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()

                if stream:
                    return await self._handle_stream(response)
                else:
                    data = response.json()
                    return data.get("response", "")

            except httpx.HTTPStatusError as e:
                # Provide actionable hint for 404 which often means the Ollama API
                # path is different or the server is not initialized with models.
                status = e.response.status_code if e.response is not None else 'unknown'
                logger.error(f"Error calling Ollama: Client error '{status}' for url '{e.request.url}'")
                if e.response is not None and e.response.status_code == 404:
                    logger.error(
                        "Ollama returned 404. Verify the Ollama server API and installed models. "
                        "Try: curl -sS {base}/api/info && curl -sS {base}/api/models".format(base=self.base_url)
                    )
                    # Try a common alternative path before giving up
                    try:
                        alt_resp = await self.client.post(f"{self.base_url}/api/v1/generate", json=payload)
                        alt_resp.raise_for_status()
                        if stream:
                            return await self._handle_stream(alt_resp)
                        return alt_resp.json().get("response", "")
                    except Exception:
                        last_exc = e
                else:
                    last_exc = e

            except httpx.RequestError as e:
                last_exc = e
                logger.error(f"Error calling Ollama (attempt {attempt}/{self._retries}): {e}")
                # exponential backoff
                if attempt < self._retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
                    continue
                else:
                    logger.error("All connection attempts failed")
                    raise
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}")
                raise
        # If loop exits without returning (e.g. unexpected), raise explicit error
        err_msg = str(last_exc) if last_exc is not None else "All connection attempts failed"
        logger.error(err_msg)
        raise RuntimeError(err_msg)
            
    async def _handle_stream(self, response) -> str:
        """Handle streaming response from Ollama."""
        full_response = ""
        async for line in response.aiter_lines():
            if line:
                try:
                    data = json.loads(line)
                    full_response += data.get("response", "")
                except json.JSONDecodeError:
                    continue
        return full_response
        
    async def analyze_incident(self, incident_description: str) -> str:
        """
        Use LLM to analyze an incident.
        
        Args:
            incident_description: Description of the incident
            
        Returns:
            Analysis and recommendations
        """
        system_prompt = """You are an expert incident response analyst. 
        Analyze the provided incident and provide:
        1. Root cause analysis
        2. Immediate mitigation steps
        3. Long-term prevention measures
        
        Be concise and actionable."""
        
        prompt = f"Analyze this incident: {incident_description}"
        
        return await self.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.5
        )
        
    async def generate_alert_summary(self, alerts: list) -> str:
        """
        Generate a summary of multiple alerts.
        
        Args:
            alerts: List of alert dictionaries
            
        Returns:
            Summary of alerts
        """
        alerts_text = "\n".join([
            f"- {alert.get('name')}: {alert.get('description')}"
            for alert in alerts
        ])
        
        system_prompt = "You are an incident summarization expert. Provide a brief, actionable summary."
        prompt = f"Summarize these alerts:\n{alerts_text}"
        
        return await self.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.3
        )
        
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Global instance
_ollama_client: Optional[OllamaClient] = None

def get_ollama_client(base_url: str | None = None, model: str | None = None) -> OllamaClient:
    """Get or create the Ollama client.

    If `base_url` is not provided, the client will read `OLLAMA_URL` or
    `OLLAMA_HOST` from the environment (compose sets `OLLAMA_URL`).
    """
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(base_url=base_url, model=model)
    return _ollama_client
