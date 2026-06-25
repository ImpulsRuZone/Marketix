from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings


class CommentGenerator:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_comment_length = settings.max_comment_length

    async def generate(self, post_text: str, account_prompt: str) -> str:
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": account_prompt
                    or "Пиши короткие, нейтральные и естественные комментарии к посту.",
                },
                {
                    "role": "user",
                    "content": post_text[:1000],
                },
            ],
            max_tokens=200,
            temperature=0.9,
        )
        content = completion.choices[0].message.content or ""
        return content.strip()[: self.max_comment_length]
