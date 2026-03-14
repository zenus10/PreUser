import logging
import time
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.config import get_settings
from app.llm.output_parser import parse_llm_json

logger = logging.getLogger(__name__)

# Suppress litellm debug logs
litellm.set_verbose = False

# Increase default timeout (seconds)
LLM_TIMEOUT = 3000


async def llm_call(
    prompt: str,
    system_prompt: str = "",
    output_format: str = "text",
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int = 8192,
    messages: list[dict] | None = None,
) -> dict | str:
    """Unified LLM call interface.

    Args:
        prompt: User prompt content
        system_prompt: System prompt (role instructions)
        output_format: "json" to parse response as JSON, "text" for raw text
        temperature: Override default temperature
        model: Override default model
        max_tokens: Maximum output tokens (default 8192)
        messages: Optional pre-built message history (for multi-turn conversations).
                  If provided, system_prompt is prepended and prompt is appended.
    """
    settings = get_settings()
    model = model or settings.llm_model
    temperature = temperature if temperature is not None else settings.llm_temperature

    if messages is not None:
        # Multi-turn: prepend system, append conversation history, then user prompt
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)
        all_messages.append({"role": "user", "content": prompt})
        messages = all_messages
    else:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

    use_json_mode = output_format == "json"

    logger.info(f"[LLM] Calling model={model}, json_mode={use_json_mode}, "
                f"max_tokens={max_tokens}, prompt_len={len(prompt)}")
    start = time.time()

    response = await _call_with_retry(model, messages, temperature, max_tokens, use_json_mode)

    elapsed = time.time() - start
    content = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    logger.info(f"[LLM] Response received in {elapsed:.1f}s, "
                f"response_len={len(content)}, "
                f"usage={usage}")

    if use_json_mode:
        parsed = parse_llm_json(content)
        logger.debug(
            f"[LLM] Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed)}")
        return parsed

    return content


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_with_retry(
    model: str,
    messages: list,
    temperature: float,
    max_tokens: int = 8192,
    json_mode: bool = False,
):
    """Call LLM with automatic retry on failure."""
    settings = get_settings()

    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=settings.deepseek_api_key,
        timeout=LLM_TIMEOUT,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        return await litellm.acompletion(**kwargs)
    except Exception as e:
        logger.warning(
            f"[LLM] Primary model {model} failed: {type(e).__name__}: {e}")
        # Try fallback model if primary fails
        if settings.llm_fallback_model and settings.llm_fallback_model != model:
            logger.info(
                f"[LLM] Trying fallback model: {settings.llm_fallback_model}")
            kwargs["model"] = settings.llm_fallback_model
            return await litellm.acompletion(**kwargs)
        raise
