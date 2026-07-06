import hashlib
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Watermark:
    user_id: str
    timestamp: float
    request_id: str
    provider: str
    model: str
    version: str = "2.0"


class TextWatermarker:
    ZERO_WIDTH = {
        '0': '\u200B',
        '1': '\u200C',
    }

    def embed(self, text: str, watermark: Watermark) -> str:
        payload = f"{watermark.user_id}:{watermark.request_id}:{int(watermark.timestamp)}"
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()[:8]
        binary = ''.join(format(ord(c), '08b') for c in payload_hash)

        sentences = text.split('. ')
        if len(sentences) < 2:
            return text

        first_sentence = sentences[0]
        words = first_sentence.split(' ')

        if len(words) < len(binary) + 1:
            watermark_chars = ''.join(self.ZERO_WIDTH[b] for b in binary)
            return text + watermark_chars

        watermarked_words = []
        for i, word in enumerate(words):
            watermarked_words.append(word)
            if i < len(binary):
                watermarked_words.append(self.ZERO_WIDTH[binary[i]])

        sentences[0] = ''.join(watermarked_words)
        return '. '.join(sentences)

    def extract(self, text: str) -> str | None:
        found = []
        for char in text:
            if char == self.ZERO_WIDTH['0']:
                found.append('0')
            elif char == self.ZERO_WIDTH['1']:
                found.append('1')

        if not found:
            return None

        binary = ''.join(found)
        if len(binary) % 8 != 0:
            binary = binary[:-(len(binary) % 8)]

        try:
            hex_str = ''.join(
                chr(int(binary[i:i+8], 2))
                for i in range(0, len(binary), 8)
            )
            return hex_str
        except ValueError:
            return None


class ImageWatermarker:
    def embed(self, image_bytes: bytes, watermark: Watermark) -> bytes:
        try:
            import io

            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            pixels = list(img.getdata())

            payload = f"{watermark.user_id}:{watermark.request_id}"
            payload_bytes = payload.encode('utf-8')

            required_pixels = (len(payload_bytes) * 8 + 2) // 3
            if len(pixels) < required_pixels:
                logger.warning("Image too small for watermark")
                return image_bytes

            length = len(payload_bytes)
            length_bytes = length.to_bytes(2, 'big')
            full_payload = length_bytes + payload_bytes

            binary_payload = ''.join(format(b, '08b') for b in full_payload)
            new_pixels = []

            bit_idx = 0
            for pixel in pixels:
                if len(pixel) >= 3:
                    r, g, b = pixel[:3]
                    if bit_idx < len(binary_payload):
                        r = (r & 0xFE) | int(binary_payload[bit_idx])
                        bit_idx += 1
                    if bit_idx < len(binary_payload):
                        g = (g & 0xFE) | int(binary_payload[bit_idx])
                        bit_idx += 1
                    if bit_idx < len(binary_payload):
                        b = (b & 0xFE) | int(binary_payload[bit_idx])
                        bit_idx += 1
                    new_pixels.append((r, g, b) + pixel[3:])
                else:
                    new_pixels.append(pixel)

            img.putdata(new_pixels)
            output = io.BytesIO()
            img.save(output, format=img.format or 'PNG')
            return output.getvalue()
        except ImportError:
            logger.warning("PIL not installed, skipping image watermark")
            return image_bytes

    def extract(self, image_bytes: bytes) -> str | None:
        try:
            import io

            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            pixels = list(img.getdata())

            bits = []
            for pixel in pixels:
                if len(pixel) >= 3:
                    bits.append(str(pixel[0] & 1))
                    bits.append(str(pixel[1] & 1))
                    bits.append(str(pixel[2] & 1))

            all_bits = ''.join(bits)
            bytes_data = bytearray()
            for i in range(0, len(all_bits), 8):
                byte = all_bits[i:i+8]
                if len(byte) == 8:
                    bytes_data.append(int(byte, 2))

            if len(bytes_data) < 2:
                return None

            length = int.from_bytes(bytes_data[:2], 'big')
            payload = bytes_data[2:2+length]
            return payload.decode('utf-8', errors='ignore')
        except Exception:
            return None


class WatermarkManager:
    def __init__(self):
        self.text = TextWatermarker()
        self.image = ImageWatermarker()

    def embed(
        self,
        content: bytes,
        content_type: str,
        watermark: Watermark
    ) -> bytes:
        if content_type.startswith("text/"):
            text = content.decode('utf-8')
            watermarked = self.text.embed(text, watermark)
            return watermarked.encode('utf-8')
        elif content_type.startswith("image/"):
            return self.image.embed(content, watermark)
        return content

    def extract(self, content: bytes, content_type: str) -> str | None:
        if content_type.startswith("text/"):
            text = content.decode('utf-8', errors='ignore')
            return self.text.extract(text)
        elif content_type.startswith("image/"):
            return self.image.extract(content)
        return None

    def encode_file(self, input_path: str, output_path: str, watermark_text: str, key: str | None = None) -> None:
        from PIL import Image
        img = Image.open(input_path)
        wm = self.encode(watermark_text, key)
        encoded = self._embed(img, wm)
        encoded.save(output_path)
