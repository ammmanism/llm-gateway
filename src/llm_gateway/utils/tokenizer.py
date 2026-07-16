import tiktoken
from typing import List, Dict, Any

def count_tokens(model: str, text: str) -> int:
    """
    Count tokens for a given text using tiktoken.
    Falls back to cl100k_base or char division if there's an error.
    """
    if not text:
        return 0
    try:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback to simple 4 characters per token estimate
        return max(1, len(text) // 4)

def count_message_tokens(model: str, messages: List[Dict[str, Any]]) -> int:
    """
    Estimate tokens in a chat prompt list.
    """
    if not messages:
        return 0
    try:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
            
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start><role/name>\n<content><im_end>\n
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += -1  # name adjustment
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    except Exception:
        # Fallback
        chars = 0
        for m in messages:
            chars += len(m.get("role", "")) + len(m.get("content", ""))
        return max(1, chars // 4)