"""
Direct Gemini API client for eSRL agents.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

class GeminiClient:
    """Wrapper for Gemini API calls."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        api_key = os.getenv('GOOGLE_API_KEY')
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.model_name = model_name

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
    ) -> str:
        """
        Generate content using Gemini

        Args:
            prompt: The user prompt/input
            system_instruction: System instruction for the model
            response_mime_type: Optional output mime type (e.g. application/json)

        Returns:
            Generated text
        """
        if not self.client:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        config = None
        if system_instruction or response_mime_type:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type=response_mime_type,
            )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )

        return response.text
