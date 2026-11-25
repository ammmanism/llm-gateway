import os

# Unit/integration tests verify span creation with fakes; they do not need a
# collector. Keeping the SDK disabled avoids background OTLP retry noise.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
