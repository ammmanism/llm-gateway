# OmniModal

> **One API. Every Modality. Zero Compromise.**

---

## What is OmniModal?

OmniModal is the missing infrastructure layer for multimodal AI. Instead of managing 15+ provider APIs, authentication schemes, rate limits, and fallback logic, you call one unified API.

```python
from omnimodal import OmniClient

client = OmniClient()

# Generate a video from text + image + audio - in one call
video = await client.fuse(
    inputs=[
        {"type": "text", "content": "A cyberpunk city at sunset"},
        {"type": "image", "content": "sketch.png"},
