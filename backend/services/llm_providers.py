"""
LLM Provider API Clients

This module contains async functions for calling various LLM APIs
with fallback strategy support.

Priority: 1. Grok (Groq) -> 2. HuggingFace -> 3. Gemini
"""

import os
import logging
import aiohttp


async def call_groq_api(prompt: str) -> str:
    """
    Call Groq API (Grok models).
    
    Args:
        prompt: The text prompt to send to the API
        
    Returns:
        The generated text response
        
    Raises:
        Exception: If API key not configured or API call fails
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise Exception("GROQ_API_KEY not configured")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7
            },
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"Groq API error: {resp.status} - {error_text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def call_huggingface_api(prompt: str) -> str:
    """
    Call HuggingFace Inference API.
    
    Uses Qwen model via router endpoint.
    
    Args:
        prompt: The text prompt to send to the API
        
    Returns:
        The generated text response
        
    Raises:
        Exception: If token not configured or API call fails
    """
    hf_token = os.getenv("HF_TOKEN_1") or os.getenv("HF_TOKEN_2")
    if not hf_token:
        raise Exception("HuggingFace token not configured")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://router.huggingface.co/novita/v3/openai/chat/completions",
            headers={
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json"
            },
            json={
                "model": "Qwen/Qwen2.5-72B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7
            },
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"HuggingFace API error: {resp.status} - {error_text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def call_gemini_api(prompt: str) -> str:
    """
    Call Google Gemini API.
    
    Args:
        prompt: The text prompt to send to the API
        
    Returns:
        The generated text response
        
    Raises:
        Exception: If API key not configured or API call fails
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise Exception("GEMINI_API_KEY not configured")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={gemini_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            },
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"Gemini API error: {resp.status} - {error_text}")
            data = await resp.json()
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content", {}).get("parts"):
                return candidates[0]["content"]["parts"][0]["text"]
            raise Exception("Unexpected Gemini response format")


async def call_with_fallback(prompt: str) -> tuple[str, str]:
    """
    Call LLM APIs with fallback strategy.
    
    Priority: 1. Grok (Groq) -> 2. HuggingFace -> 3. Gemini
    
    Args:
        prompt: The text prompt to send
        
    Returns:
        Tuple of (result_text, provider_used)
        
    Raises:
        Exception: If all providers fail
    """
    result = None
    provider_used = None
    errors = []
    
    # Try Groq first
    try:
        logging.info("Attempting Groq API...")
        result = await call_groq_api(prompt)
        provider_used = "groq"
        logging.info("✅ Groq API succeeded")
        return result, provider_used
    except Exception as e:
        errors.append(f"Groq: {str(e)}")
        logging.warning(f"Groq API failed: {e}")
    
    # Try HuggingFace if Groq failed
    try:
        logging.info("Attempting HuggingFace API...")
        result = await call_huggingface_api(prompt)
        provider_used = "huggingface"
        logging.info("✅ HuggingFace API succeeded")
        return result, provider_used
    except Exception as e:
        errors.append(f"HuggingFace: {str(e)}")
        logging.warning(f"HuggingFace API failed: {e}")
    
    # Try Gemini as final fallback
    try:
        logging.info("Attempting Gemini API...")
        result = await call_gemini_api(prompt)
        provider_used = "gemini"
        logging.info("✅ Gemini API succeeded")
        return result, provider_used
    except Exception as e:
        errors.append(f"Gemini: {str(e)}")
        logging.warning(f"Gemini API failed: {e}")
    
    raise Exception(f"All AI providers failed: {errors}")
