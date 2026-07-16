import time

import pytest
from omnimodal.core.watermark import (
    ImageWatermarker,
    TextWatermarker,
    Watermark,
    WatermarkManager,
)


class TestTextWatermarker:
    def test_embed_and_extract(self):
        watermarker = TextWatermarker()
        wm = Watermark(
            user_id="user-123",
            timestamp=time.time(),
            request_id="req-456",
            provider="openai",
            model="gpt-4o",
        )

        original = "This is a test sentence. It has two sentences."
        watermarked = watermarker.embed(original, wm)
        assert watermarked != original
        assert len(watermarked) >= len(original)

        extracted = watermarker.extract(watermarked)
        assert extracted is not None
        assert len(extracted) == 8

    def test_no_watermark(self):
        watermarker = TextWatermarker()
        plain_text = "Hello world"
        extracted = watermarker.extract(plain_text)
        assert extracted is None

    def test_short_text(self):
        watermarker = TextWatermarker()
        wm = Watermark("u1", time.time(), "r1", "openai", "gpt-4o")
        short = "This is a short text. It has two sentences here."
        watermarked = watermarker.embed(short, wm)
        assert watermarked != short


class TestImageWatermarker:
    def test_embed_and_extract(self):
        pytest.importorskip("PIL")
        import io

        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        watermarker = ImageWatermarker()
        wm = Watermark("u1", time.time(), "r1", "openai", "dall-e-3")

        watermarked = watermarker.embed(img_bytes, wm)
        assert watermarked != img_bytes

        extracted = watermarker.extract(watermarked)
        assert extracted is not None
        assert "u1" in extracted

    def test_no_watermark(self):
        pytest.importorskip("PIL")
        extracted = ImageWatermarker().extract(b"not an image")
        assert extracted is None


class TestWatermarkManager:
    def test_text_roundtrip(self):
        mgr = WatermarkManager()
        wm = Watermark("u1", time.time(), "r1", "openai", "gpt-4o")
        text = b"Hello world. This has multiple sentences."
        watermarked = mgr.embed(text, "text/plain", wm)
        extracted = mgr.extract(watermarked, "text/plain")
        assert extracted is not None

    def test_unsupported_type(self):
        mgr = WatermarkManager()
        wm = Watermark("u1", time.time(), "r1", "openai", "gpt-4o")
        result = mgr.embed(b"data", "audio/mp3", wm)
        assert result == b"data"
