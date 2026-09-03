"""
Generates a comment for a post using OpenAI GPT.
Each account can have its own gpt_prompt stored in the DB.
"""

from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY, DEFAULT_GPT_PROMPT, MAX_COMMENT_LENGTH

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def _truncate_comment(text: str, max_len: int) -> str:
    """Cut to max_len without breaking mid-word when possible."""
    text = (text or "").strip()
    if max_len <= 0 or len(text) <= max_len:
        return text
    cut = text[:max_len].rstrip()
    # Prefer last whitespace so we don't end on "уж н"
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    return cut


async def generate_comment(post_text: str, account_prompt: str | None = None) -> str:
    """
    Generates a comment.
    account_prompt overrides DEFAULT_GPT_PROMPT if provided.
    """
    system_prompt = account_prompt or DEFAULT_GPT_PROMPT

    response = await _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": post_text[:1000]},
        ],
        max_tokens=400,
        temperature=0.9,
    )
    comment = response.choices[0].message.content.strip()
    return _truncate_comment(comment, MAX_COMMENT_LENGTH)
