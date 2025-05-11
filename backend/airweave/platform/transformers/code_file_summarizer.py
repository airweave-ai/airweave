"""Code file summarizer."""

import logging

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import CodeFileEntity

logger = logging.getLogger(__name__)


@transformer(name="Code File Summarizer")
async def code_file_summarizer(file: CodeFileEntity) -> CodeFileEntity:
    """Summarize a code file."""
    logger.info(f"Starting code file summarizer for file: {file.name} (file_id: {file.file_id})")

    if not settings.CODE_SUMMARIZER_ENABLED:
        logger.info("Code summarizer is disabled, skipping summarization")
        return file

    PROMPT = f"""
    Summarize the following code file in a short and concise manner. Just return the smallest
    possible summary, do not include any other text:
    ```
    {file.content}
    ```

    """

    file_summary = None
    if settings.ANTHROPIC_API_KEY:
        logger.info("Using Anthropic API for code summarization")
        client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
        )
        # Get the summary
        try:
            logger.debug("Sending request to Anthropic API")
            summary = await client.messages.create(
                max_tokens=8192,
                messages=[
                    {
                        "role": "user",
                        "content": PROMPT,
                    }
                ],
                model="claude-3-5-haiku-20241022",
            )
            file_summary = summary.content[0].text
            logger.debug(f"Received summary from Anthropic API, length: {len(file_summary)}")
        except Exception as e:
            logger.error(f"Error using Anthropic API: {str(e)}")
            raise

    else:
        logger.info("Using OpenAI API for code summarization")
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Get the summary
        try:
            logger.debug("Sending request to OpenAI API")
            summary = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": PROMPT}],
            )
            file_summary = summary.choices[0].message.content
            logger.debug(f"Received summary from OpenAI API, length: {len(file_summary)}")
        except Exception as e:
            logger.error(f"Error using OpenAI API: {str(e)}")
            raise

    # Update the file with the summary
    file.summary = file_summary
    logger.info(f"Completed code file summarization for {file.name}")

    return file
