"""Functions for interfacing with LLMs."""

from typing import Literal

import openai
from loguru import logger

client = openai.OpenAI()


def prompt_llm(
    prompt: str,
    *,
    model: Literal["gpt-4o"] = "gpt-4o",
    temperature: float | None = None,
) -> str:
    """Prompt GPT with a basic string and return the result.

    Args:
        prompt: The prompt to send to GPT.
        model: The model to use. Default is "gpt-4o".
        temperature: The temperature to use. Lower is "less creative".
            If None, the default for the model is used.

    Return:
        The result from GPT.

    """
    response = client.responses.create(
        model=model,
        input=prompt,
        temperature=temperature,
    )

    logger.debug(
        f"Prompted LLM (prompt={len(prompt):} bytes, "
        f"response={len(response.output_text):} bytes)."
    )

    reply = response.output_text
    return reply.strip()


if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    logger.debug(f"User prompt: {prompt}")
    response = prompt_llm(prompt)
    logger.info(f"LLM response: {response}")
