from __future__ import annotations
from google import genai
from google.genai import types


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", max_tokens: int = 2000):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: str, system: str = "") -> str:
        config = types.GenerateContentConfig(
            system_instruction=system if system else None,
            max_output_tokens=self._max_tokens,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text
