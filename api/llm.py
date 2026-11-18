import random
import time

from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError, InternalServerError

from api.config import BASE_URL, DEEPSEEK_API_KEY, MODEL

BASE_DELAY = 2

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=BASE_URL,
    max_retries=0
)

RETRYABLE = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)

class UpstreamTimeout(Exception):
    """上游超时或重试耗尽"""
    pass

def create_with_retry(msgs, *, deadline, tools=None, request_id="", max_attempts=3):
    for attempt in range(max_attempts):
        t_attempt = time.monotonic()
        try:
            kwargs = dict(model=MODEL, messages=msgs, timeout=max(1, min(deadline - t_attempt, 15)))
            if tools:
                kwargs["tools"] = tools
            return client.chat.completions.create(**kwargs)

        except RETRYABLE as e:
            took = time.monotonic() - t_attempt
            delay = BASE_DELAY * (2 ** attempt) * random.uniform(0.5, 1.5)
            print(f"[retry] attempt={attempt} 单次耗时={took:.2f}s exc={type(e).__name__} "
                  f"delay={delay:.2f}s 已用={time.monotonic() - (deadline - 60):.2f}s", flush=True)

            if attempt == max_attempts - 1:
                raise UpstreamTimeout(f"重试耗尽：{type(e).__name__}") from e

            if time.monotonic() + delay > deadline:
                raise UpstreamTimeout(f"重试耗尽：第 {attempt+1} 次等待 {delay:.1f}s 会超预算") from e
            time.sleep(delay)
    raise UpstreamTimeout("重试耗尽")
