from __future__ import annotations

from openai import OpenAI

from app.config import settings


class CommentGenerator:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def generate(self, post_text: str, account_prompt: str) -> str:
        completion = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You generate short, human-like Telegram comments. "
                        "Never claim facts not present in the post."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Account prompt:\n{account_prompt}\n\n"
                        f"Post text:\n{post_text}\n\n"
                        "Generate one comment in plain text."
                    ),
                },
            ],
            temperature=0.7,
            max_output_tokens=120,
        )
        return completion.output_text.strip()
