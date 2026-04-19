from typing import Protocol


class AIProvider(Protocol):
    def generate(self, prompt: str, system: str = "") -> str: ...
