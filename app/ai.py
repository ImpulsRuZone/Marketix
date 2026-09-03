from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY, SYSTEM_PROMPT, MAX_COMMENT_LENGTH

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_comment(post_text: str) -> str:
    response = await _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": post_text[:1000]},
        ],
        max_tokens=200,
        temperature=0.9,
    )
    comment = response.choices[0].message.content.strip()
    return comment[:MAX_COMMENT_LENGTH]
