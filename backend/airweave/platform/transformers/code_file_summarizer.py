"""Code file summarizer."""

from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import CodeFileEntity


@transformer(name="Code File Summarizer")
async def code_file_summarizer(file: CodeFileEntity) -> CodeFileEntity:
    """Summarize a code file."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    PROMPT = f"""
    Summarize the following code file in a short and concise manner. Just return the smallest
    possible summary, do not include any other text:
    ```
    {file.content}
    ```
    """

    # Get the summary
    summary = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": PROMPT}],
    )

    # Update the file with the summary
    file.summary = summary.choices[0].message.content

    return file
