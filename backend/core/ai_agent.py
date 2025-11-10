"""
AI Agent with provider failover and streaming capabilities.

This script defines an AiAgent class that can interact with multiple
LLM providers (Groq, HuggingFace) with a unified interface.

Key Features:
- Provider Failover: Automatically tries the next provider if one fails.
- Streaming Support: Supports streaming responses from Groq and HuggingFace.
- Blocking Calls: Supports traditional request-response blocking calls.
- Unified Response: Returns a standardized `AiResponse` object for blocking calls.
- Metrics Tracking: Keeps basic metrics on success, failure, latency, and time-to-first-token.
- Official SDKs: Uses official 'groq' and 'huggingface_hub' libraries for reliability.
"""
from __future__ import annotations

import logging
import time
import copy
import random
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Iterator, Dict, Any

# --- SDK Imports ---
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError
from groq import Groq, GroqError as GroqSDKError # Import the official Groq client and its error class

# --- Import Configuration from config.py ---
from core.config import (
    HF_TOKENS, 
    GROQ_API_KEY, 
    SUPPORTED_MODELS, 
    DEFAULT_MODEL,
    PROVIDER_SEQUENCE_DEFAULT,
    SINGLE_MODE,
    SINGLE_PROVIDER
)


# --- Custom Exceptions ---
class ConfigurationError(Exception):
    """Raised for configuration-related errors."""
    pass

class ProviderError(Exception):
    """Base class for provider-specific errors."""
    pass

class HuggingFaceError(ProviderError):
    """Raised for errors specific to the HuggingFace provider."""
    pass

class GroqError(ProviderError):
    """Raised for errors specific to the Groq provider."""
    pass

class NoProviderAvailableError(Exception):
    """Raised when all providers in the sequence have failed."""
    pass


# --- Unified Response Object ---
@dataclass
class AiResponse:
    """A structured response object for AI agent calls."""
    text: str
    provider: str
    latency: float
    raw_response: Any


class AiAgent:
    """
    An AI agent that provides a unified interface for multiple LLM providers,
    featuring failover, streaming, and performance metrics.
    """
    HF_DEFAULT_TIMEOUT = 30

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model_name = model_name
        self.hf_client = None
        self.groq_client = None
        self._initialize_clients()

        # Metrics Tracking
        self.metrics = {
            "success": defaultdict(int),
            "failure": defaultdict(int),
            "latency": defaultdict(list),
            "latency_first_token": defaultdict(list), # New metric for streaming
            "retries": defaultdict(int) # Note: retry logic not yet implemented, but metric is ready
        }
        self.last_raw_response = None
        self.last_errors = {}

    def _initialize_clients(self):
        """Initializes API clients based on available credentials."""
        # Validate that keys are not placeholders
        if not HF_TOKENS or HF_TOKENS == [""]:
            self.logger.warning("HuggingFace tokens not configured. HF provider will be unavailable.")
        else:
            # Round-robin token selection for HuggingFace
            hf_token = random.choice(HF_TOKENS)
            self.hf_client = InferenceClient(token=hf_token)
            self.logger.info("HuggingFace client initialized.")

        if not GROQ_API_KEY or GROQ_API_KEY == "":
            self.logger.warning("GROQ_API_KEY not configured. Groq provider will be unavailable.")
        else:
            self.groq_client = Groq(api_key=GROQ_API_KEY)
            self.logger.info("Groq client initialized.")

    def _update_metrics(self, provider: str, success: bool, latency: float, latency_first_token: Optional[float] = None):
        """Updates performance metrics for a given provider."""
        if success:
            self.metrics["success"][provider] += 1
            self.metrics["latency"][provider].append(latency)
            if latency_first_token is not None:
                self.metrics["latency_first_token"][provider].append(latency_first_token)
        else:
            self.metrics["failure"][provider] += 1

    def _get_provider_sequence(self, providers: Optional[List[str]]) -> List[str]:
        """
        Determines the sequence of providers to use for a request.
        If SINGLE_MODE is disabled, it will try all providers in sequence (failover).
        """
        if SINGLE_MODE and SINGLE_PROVIDER:
            self.logger.info(f"SINGLE_MODE enabled, using only: {SINGLE_PROVIDER}")
            return [SINGLE_PROVIDER]
        if providers:
            return providers
        # Default: Try Groq first, then fallback to HuggingFace
        self.logger.info(f"Using provider sequence: {PROVIDER_SEQUENCE_DEFAULT}")
        return PROVIDER_SEQUENCE_DEFAULT

    def _call_huggingface(self, user_message: str, system_prompt: Optional[str], max_tokens: int) -> AiResponse:
        """Makes a blocking call to the HuggingFace Inference API."""
        if not self.hf_client:
            raise HuggingFaceError("HuggingFace client not initialized. Check API keys.")

        model_id = SUPPORTED_MODELS.get(self.model_name, {}).get('huggingface')
        if not model_id:
            raise ConfigurationError(f"HuggingFace model for '{self.model_name}' not configured.")

        prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_message}\n<|assistant|>" if system_prompt else user_message
        
        start_time = time.time()
        try:
            response_text = self.hf_client.text_generation(
                prompt=prompt,
                model=model_id,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
            )
            latency = time.time() - start_time
            return AiResponse(text=response_text, provider="huggingface", latency=latency, raw_response={"response": response_text})
        
        except HfHubHTTPError as e:
            error_msg = str(e)
            if "401" in error_msg or "403" in error_msg:
                self.logger.error(f"HuggingFace authentication failed. Check HF_TOKEN in .env file.")
                raise HuggingFaceError(f"Authentication failed - Invalid HuggingFace token. Get a token from https://huggingface.co/settings/tokens") from e
            elif "503" in error_msg or "loading" in error_msg.lower():
                self.logger.warning(f"HuggingFace model is loading. This may take a minute...")
                raise HuggingFaceError(f"Model is loading. Please try again in a moment.") from e
            else:
                self.logger.error(f"HuggingFace API Error: {e}")
                raise HuggingFaceError(f"API Error: {e.response.status_code} - {e.response.text}") from e
        except Exception as e:
            self.logger.error(f"An unexpected error occurred with HuggingFace: {e}")
            raise HuggingFaceError(f"Unexpected Error: {str(e)}") from e

    def _call_groq(self, user_message: str, system_prompt: Optional[str], max_tokens: int, stream: bool = False) -> Iterator[str]:
        """
        Makes a call to the Groq API using the official SDK.
        This single method handles both blocking and streaming responses.
        """
        if not self.groq_client:
            raise GroqError("Groq client not initialized. Check API key.")

        model_id = SUPPORTED_MODELS.get(self.model_name, {}).get('groq')
        if not model_id:
            raise ConfigurationError(f"Groq model for '{self.model_name}' not configured.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        
        try:
            response_stream = self.groq_client.chat.completions.create(
                model=model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=stream,
            )

            if not stream:
                # Blocking: yield a single result and stop.
                yield response_stream.choices[0].message.content
                return

            # Streaming: yield content from each chunk in the stream.
            for chunk in response_stream:
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content

        except GroqSDKError as e:
            error_msg = str(e)
            if "401" in error_msg or "Invalid API Key" in error_msg:
                self.logger.error(f"Groq API Key is invalid or expired. Please update GROQ_API_KEY in .env file.")
                raise GroqError(f"Authentication failed - Invalid or expired API key. Get a new key from https://console.groq.com/keys") from e
            elif "429" in error_msg or "rate_limit" in error_msg.lower():
                self.logger.error(f"Groq rate limit exceeded. Trying fallback provider...")
                raise GroqError(f"Rate limit exceeded. Will try alternate provider.") from e
            else:
                self.logger.error(f"Groq SDK Error: {e}")
                raise GroqError(f"Groq SDK Error: {e.__class__.__name__} - {e}") from e
        except Exception as e:
            self.logger.error(f"An unexpected error occurred with Groq: {e}")
            raise GroqError(f"Unexpected Error: {str(e)}") from e

    def call_blocking(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        providers: Optional[List[str]] = None
    ) -> AiResponse:
        """
        Calls AI providers in a specified sequence with failover for a complete,
        blocking response.
        """
        provider_sequence = self._get_provider_sequence(providers)
        self.last_errors.clear()

        for provider in provider_sequence:
            try:
                response = None
                self.logger.info(f"Attempting blocking call with provider: {provider}")
                start_time = time.time()
                
                if provider == 'huggingface':
                    response = self._call_huggingface(user_message, system_prompt, max_tokens)
                
                elif provider == 'groq':
                    text_chunks = list(self._call_groq(user_message, system_prompt, max_tokens, stream=False))
                    full_text = "".join(text_chunks)
                    if not full_text:
                        raise GroqError("Received an empty response from provider.")
                    
                    response = AiResponse(
                        text=full_text, provider="groq", latency=0, raw_response=None # Latency calculated below
                    )
                else:
                    raise ConfigurationError(f"Provider '{provider}' is not supported.")

                latency = time.time() - start_time
                response.latency = latency # Update latency for all providers
                
                self._update_metrics(provider, success=True, latency=latency)
                self.last_raw_response = response.raw_response
                self.logger.info(f"Success from {provider} in {latency:.2f}s.")
                return response

            except ProviderError as e:
                self.logger.warning(f"Provider '{provider}' failed: {e}")
                self._update_metrics(provider, success=False, latency=0)
                self.last_errors[provider] = {"type": e.__class__.__name__, "message": str(e)}

        raise NoProviderAvailableError("All configured AI providers failed for blocking call.")

    def _stream_hf(self, user_message: str, max_tokens: int, system_prompt: Optional[str]) -> Iterator[str]:
        """Streams response from HuggingFace."""
        if not self.hf_client:
            raise HuggingFaceError("HuggingFace client not initialized for streaming.")

        model_id = SUPPORTED_MODELS.get(self.model_name, {}).get('huggingface')
        if not model_id:
            raise ConfigurationError(f"HuggingFace model for '{self.model_name}' not configured.")

        prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_message}\n<|assistant|>" if system_prompt else user_message

        try:
            for token in self.hf_client.text_generation(
                prompt=prompt, model=model_id, max_new_tokens=max_tokens,
                stream=True, do_sample=True, temperature=0.7, top_p=0.95,
            ):
                yield token
        except HfHubHTTPError as e:
            error_msg = str(e)
            if "not supported" in error_msg.lower() or "task" in error_msg.lower():
                self.logger.warning(f"HuggingFace model configuration issue: {error_msg}")
                raise HuggingFaceError(f"Model configuration error. Trying alternate provider...") from e
            raise HuggingFaceError(f"API Error during streaming: {e.response.status_code}") from e
        except Exception as e:
            raise HuggingFaceError(f"Unexpected streaming error: {str(e)}") from e

    def stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        providers: Optional[List[str]] = None
    ) -> Iterator[str]:
        """
        Attempts to stream a response from the providers in sequence.
        The first successful provider will be used. Captures time-to-first-token metric.
        """
        provider_sequence = self._get_provider_sequence(providers)
        self.last_errors.clear()

        for provider in provider_sequence:
            try:
                self.logger.info(f"Attempting to stream with provider: {provider}")
                start_time = time.time()
                
                stream_generator = None
                if provider == 'groq':
                    stream_generator = self._call_groq(user_message, system_prompt, max_tokens, stream=True)
                elif provider == 'huggingface':
                    stream_generator = self._stream_hf(user_message, max_tokens, system_prompt)
                else:
                    raise ConfigurationError(f"Provider '{provider}' is not supported.")

                # Manually iterate to capture first token time
                first_token_time = None
                for chunk in stream_generator:
                    if first_token_time is None:
                        first_token_time = time.time()
                    yield chunk

                # If we get here, the stream was successful
                end_time = time.time()
                total_latency = end_time - start_time
                latency_ttft = first_token_time - start_time if first_token_time else 0
                
                self._update_metrics(provider, success=True, latency=total_latency, latency_first_token=latency_ttft)
                self.logger.info(
                    f"Successfully streamed from {provider}. "
                    f"TTFT: {latency_ttft:.2f}s, Total Latency: {total_latency:.2f}s."
                )
                return # Exit after the first successful stream

            except ProviderError as e:
                self.logger.warning(f"Streaming with provider '{provider}' failed: {e}. Trying next.")
                self._update_metrics(provider, success=False, latency=0)
                self.last_errors[provider] = {"type": e.__class__.__name__, "message": str(e)}

        raise NoProviderAvailableError("All configured AI providers failed to stream.")

    # --- Metrics & Data Accessors ---
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        return copy.deepcopy(self.metrics)

    def get_last_raw_response(self) -> Optional[Any]:
        return self.last_raw_response
    
    def get_last_errors(self) -> Dict[str, Dict[str, str]]:
        return self.last_errors.copy()

    def get_success_rate(self, provider: str) -> float:
        successes = self.metrics["success"].get(provider, 0)
        failures = self.metrics["failure"].get(provider, 0)
        total = successes + failures
        return (successes / total) if total > 0 else 1.0

    def get_average_latency(self, provider: str) -> float:
        latencies = self.metrics["latency"].get(provider, [])
        return sum(latencies) / len(latencies) if latencies else 0.0
        
    def get_average_first_token_latency(self, provider: str) -> float:
        """Gets the average time to the first token for a streaming provider."""
        latencies = self.metrics["latency_first_token"].get(provider, [])
        return sum(latencies) / len(latencies) if latencies else 0.0


