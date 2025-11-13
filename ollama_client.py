"""
Ollama Client for both local and Modal deployments.

This module provides a unified interface for Ollama inference that works
with both local Ollama instances and Modal's serverless GPU functions.

Usage:
    from ollama_client import OllamaClient

    client = OllamaClient()
    response = client.generate(model="f1-analyst:latest", prompt="...")
"""

import os
import requests
import logging
from typing import Dict, Optional, Iterator

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Unified Ollama client supporting local and Modal deployments.

    When MODAL_DEPLOYMENT=true, uses Modal's remote GPU functions.
    Otherwise, uses local Ollama instance.
    """

    def __init__(self, base_url: Optional[str] = None, use_modal: Optional[bool] = None):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama base URL (default: from OLLAMA_BASE_URL env var)
            use_modal: Force Modal usage (default: from MODAL_DEPLOYMENT env var)
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.use_modal = use_modal if use_modal is not None else os.getenv("MODAL_DEPLOYMENT", "false").lower() == "true"

        if self.use_modal:
            logger.info("Using Modal serverless GPU for Ollama inference")
            try:
                from modal import Function
                self.modal_generate = Function.lookup("f1-telemetry", "run_ollama_generate")
                logger.info("✓ Connected to Modal function")
            except ImportError:
                logger.error("Modal not installed. Install with: pip install modal")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Modal: {e}")
                raise
        else:
            logger.info(f"Using local Ollama at {self.base_url}")

    def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict] = None,
        stream: bool = False,
        timeout: int = 60,
    ) -> Dict:
        """
        Generate completion using Ollama.

        Args:
            model: Model name (e.g., "f1-analyst:latest")
            prompt: Input prompt
            options: Model options (temperature, etc.)
            stream: Whether to stream the response
            timeout: Request timeout in seconds

        Returns:
            dict: Response from Ollama

        Example:
            >>> client = OllamaClient()
            >>> response = client.generate(
            ...     model="f1-analyst:latest",
            ...     prompt="Explain trail braking",
            ...     options={"temperature": 0.1}
            ... )
            >>> print(response["response"])
        """
        if self.use_modal:
            return self._generate_modal(model, prompt, options, stream)
        else:
            return self._generate_local(model, prompt, options, stream, timeout)

    def _generate_local(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict],
        stream: bool,
        timeout: int,
    ) -> Dict:
        """Generate using local Ollama instance."""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if options:
            payload["options"] = options

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=timeout,
                stream=stream,
            )
            response.raise_for_status()

            if stream:
                # Handle streaming response
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        import json
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response += chunk["response"]
                        if chunk.get("done", False):
                            return {
                                "response": full_response,
                                "model": model,
                                "done": True,
                            }
                return {"response": full_response, "model": model}
            else:
                return response.json()

        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after {timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Ollama generation: {e}")
            raise

    def _generate_modal(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict],
        stream: bool,
    ) -> Dict:
        """Generate using Modal serverless GPU."""
        try:
            logger.info(f"Calling Modal function for model: {model}")
            result = self.modal_generate.remote(
                model=model,
                prompt=prompt,
                options=options,
                stream=stream,
            )
            logger.info("✓ Modal inference completed")
            return result

        except Exception as e:
            logger.error(f"Modal inference failed: {e}")
            # Fallback to local if Modal fails
            if not self.use_modal:
                logger.warning("Attempting local fallback...")
                return self._generate_local(model, prompt, options, stream, 60)
            raise

    def check_health(self) -> bool:
        """
        Check if Ollama service is healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        if self.use_modal:
            try:
                from modal import Function
                # Check if Modal function exists
                Function.lookup("f1-telemetry", "run_ollama_generate")
                return True
            except Exception as e:
                logger.error(f"Modal health check failed: {e}")
                return False
        else:
            try:
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Local Ollama health check failed: {e}")
                return False

    def list_models(self) -> list:
        """
        List available models.

        Returns:
            list: List of model names
        """
        if self.use_modal:
            # Modal doesn't have a list API, return expected models
            return ["f1-analyst:latest"]
        else:
            try:
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
                response.raise_for_status()
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            except Exception as e:
                logger.error(f"Failed to list models: {e}")
                return []


# Global client instance (lazy initialized)
_client: Optional[OllamaClient] = None


def get_client() -> OllamaClient:
    """
    Get global Ollama client instance.

    This creates a singleton client that's reused across requests.

    Returns:
        OllamaClient: Global client instance
    """
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


# Convenience functions
def generate(model: str, prompt: str, **kwargs) -> Dict:
    """
    Convenience function for generation.

    Args:
        model: Model name
        prompt: Input prompt
        **kwargs: Additional options (temperature, stream, etc.)

    Returns:
        dict: Response from Ollama
    """
    client = get_client()
    return client.generate(model, prompt, **kwargs)


def check_health() -> bool:
    """
    Convenience function to check Ollama health.

    Returns:
        bool: True if healthy, False otherwise
    """
    client = get_client()
    return client.check_health()
