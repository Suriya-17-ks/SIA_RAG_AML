"""
Unified LLM Adapter Layer for SIA-RAG

This module provides a consistent interface for all LLM providers:
- OpenAI (paid)
- Ollama (free, local)
- Google Gemini (free tier)
- Groq (free tier)

All adapters expose an OpenAI-compatible interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import json
import re


class ChatMessage:
    """Standardized chat message format."""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class ChatCompletion:
    """Standardized chat completion response."""
    def __init__(self, content: str):
        self.choices = [type('obj', (object,), {
            'message': type('obj', (object,), {'content': content})()
        })()]


class BaseLLMAdapter(ABC):
    """Base adapter interface that all LLM providers must implement."""
    
    @abstractmethod
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Create a chat completion.
        
        Args:
            model: Model name/identifier
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            response_format: Optional format specification (e.g., {"type": "json_object"})
            **kwargs: Provider-specific options
            
        Returns:
            ChatCompletion object with standardized interface
        """
        pass
    
    @abstractmethod
    def supports_json_mode(self) -> bool:
        """Whether this provider supports native JSON mode."""
        pass


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and OpenAI-compatible APIs (Groq, Ollama)."""
    
    def __init__(self, client):
        """
        Args:
            client: OpenAI client instance
        """
        self.client = client
    
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ChatCompletion:
        """Create chat completion using OpenAI API."""
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        # Add JSON mode if requested
        if response_format:
            params["response_format"] = response_format
        
        response = self.client.chat.completions.create(**params)
        return response
    
    def supports_json_mode(self) -> bool:
        return True


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        Args:
            api_key: Google API key
            model_name: Gemini model name
        """
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
    
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Create chat completion using Gemini API.
        
        Note: Gemini doesn't support OpenAI's exact interface, so we convert:
        - Messages are converted to Gemini's format
        - JSON mode is handled via prompt instructions
        """
        # Extract system message if present
        system_instruction = None
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                user_messages.append(msg["content"])
            elif msg["role"] == "assistant":
                # Gemini doesn't need assistant messages in simple completions
                pass
        
        # Build the prompt
        prompt = "\n\n".join(user_messages)
        
        # If JSON mode is requested, add explicit instructions
        if response_format and response_format.get("type") == "json_object":
            json_instruction = "\n\nYou MUST respond with valid JSON only. No additional text, explanations, or markdown formatting. Just pure JSON."
            if system_instruction:
                system_instruction += json_instruction
            else:
                prompt = json_instruction + "\n\n" + prompt
        
        # Configure generation with system instruction if available
        generation_config = {
            "temperature": temperature,
        }
        
        # Recreate model with system instruction if needed
        if system_instruction:
            import google.generativeai as genai
            model_with_system = genai.GenerativeModel(
                self.model_name,
                system_instruction=system_instruction
            )
            response = model_with_system.generate_content(
                prompt,
                generation_config=generation_config
            )
        else:
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
        
        # Extract text from response
        content = response.text
        
        # If JSON mode was requested, try to clean up the response
        if response_format and response_format.get("type") == "json_object":
            content = self._extract_json(content)
        
        # Return in OpenAI-compatible format
        return ChatCompletion(content)
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from potentially markdown-formatted response."""
        # Remove markdown code blocks if present
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()
        
        # Try to find JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return text
    
    def supports_json_mode(self) -> bool:
        return False  # Gemini doesn't have native JSON mode, but we handle it


class OllamaAdapter(OpenAIAdapter):
    """
    Adapter for Ollama (uses OpenAI-compatible API).
    Inherits from OpenAIAdapter since Ollama supports OpenAI protocol.
    """
    def supports_json_mode(self) -> bool:
        return True  # Ollama supports JSON mode


class GroqAdapter(OpenAIAdapter):
    """
    Adapter for Groq (uses OpenAI-compatible API).
    Inherits from OpenAIAdapter since Groq supports OpenAI protocol.
    """
    def supports_json_mode(self) -> bool:
        return True  # Groq supports JSON mode


class HuggingFaceAdapter(BaseLLMAdapter):
    """
    Adapter for HuggingFace Inference API using huggingface_hub.InferenceClient.

    Uses the official HF client which automatically routes to the correct
    endpoint (router.huggingface.co) — bypassing the deprecated
    api-inference.huggingface.co domain.
    """

    def __init__(self, api_key: str, model: str):
        from huggingface_hub import InferenceClient
        self._model  = model
        self._client = InferenceClient(model=model, token=api_key)

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Call HF Inference API via InferenceClient.
        JSON mode is handled via system-prompt injection + fence stripping.
        """
        json_mode = (
            response_format is not None
            and response_format.get("type") == "json_object"
        )

        patched_messages = list(messages)
        if json_mode:
            # Inject JSON instruction into system message
            injected = False
            for i, msg in enumerate(patched_messages):
                if msg["role"] == "system" and not injected:
                    patched_messages[i] = {
                        "role":    "system",
                        "content": msg["content"] + "\n\nRespond with valid JSON only. No markdown, no explanation.",
                    }
                    injected = True
            if not injected:
                patched_messages.insert(0, {
                    "role":    "system",
                    "content": "Respond with valid JSON only. No markdown, no explanation.",
                })

        # model argument is ignored — InferenceClient uses self._model
        response = self._client.chat_completion(
            messages=patched_messages,
            temperature=temperature,
            max_tokens=min(kwargs.get("max_tokens", 512), 512),   # free tier cap
        )

        content = response.choices[0].message.content or ""

        if json_mode:
            # Strip ```json … ``` fences some models emit
            content = re.sub(r"^```json\s*", "", content, flags=re.MULTILINE)
            content = re.sub(r"^```\s*$",    "", content, flags=re.MULTILINE)
            content = content.strip()

        return ChatCompletion(content)

    def supports_json_mode(self) -> bool:
        return True  # handled via prompt injection


class FallbackAdapter(BaseLLMAdapter):
    """
    Adapter that tries a primary provider and falls back to a secondary provider on failure.
    Useful for handling rate limits or credits exhaustion automatically.
    """
    def __init__(self, primary: BaseLLMAdapter, fallback: BaseLLMAdapter):
        self.primary = primary
        self.fallback = fallback

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ChatCompletion:
        try:
            return self.primary.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                **kwargs
            )
        except Exception as e:
            print(f"[FallbackAdapter] Primary LLM failed: {e}. Switching to fallback...")
            
            # Note: We don't pass the exact same model string to the fallback unless we know it supports it
            # The calling code should ideally use settings.verifier_model or let the fallback use its default.
            # But the fallback adapter handles its own models under the hood based on settings.
            
            # If the fallback is an OpenAIAdapter targeting OpenRouter, we need its specific model.
            from backend.config.settings import settings
            fallback_model = model
            if hasattr(self.fallback, 'client') and hasattr(self.fallback.client, 'base_url'):
                if "openrouter" in str(self.fallback.client.base_url):
                    # We need to map `model` back to the fallback's model based on role
                    if model == settings.verifier_model or model == settings.groq_model:
                        fallback_model = settings.openrouter_verifier_model
                    else:
                        fallback_model = settings.openrouter_router_model

            return self.fallback.chat_completion(
                model=fallback_model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                **kwargs
            )

    def supports_json_mode(self) -> bool:
        # We assume json mode is supported if either adapter supports it.
        # But specifically, if primary supports it, we return True. 
        # If it falls back, we hope fallback supports it too.
        return self.primary.supports_json_mode() or self.fallback.supports_json_mode()


