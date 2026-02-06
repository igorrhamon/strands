"""
Ollama LLM client for Strands.

Provides integration with locally-running Ollama for LLM capabilities.
"""

import httpx
import logging
from typing import Optional, AsyncGenerator
import json

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with Ollama LLM."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=300.0)
        
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
                
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            raise
            
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

def get_ollama_client(base_url: str = "http://localhost:11434") -> OllamaClient:
    """Get or create the Ollama client."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(base_url=base_url)
    return _ollama_client
