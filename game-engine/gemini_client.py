"""
Direct Gemini API client for eSRL agents
"""

import os
from google import genai
from google.genai import types
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class GeminiClient:
    """Wrapper for Gemini API calls"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Generate content using Gemini

        Args:
            prompt: The user prompt/input
            system_instruction: System instruction for the model

        Returns:
            Generated text
        """
        config = None
        if system_instruction:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction
            )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )

        return response.text
