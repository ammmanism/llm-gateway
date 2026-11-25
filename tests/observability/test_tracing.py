from unittest.mock import MagicMock

from llm_gateway.observability.tracing import open_telemetry


def test_init_tracing_honors_disabled_switch(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    assert open_telemetry.init_tracing() is None


def test_init_tracing_wires_otlp_exporter(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

    provider = MagicMock()
    exporter = MagicMock()
    processor = MagicMock()
    monkeypatch.setattr(
        open_telemetry, "TracerProvider", MagicMock(return_value=provider)
    )
    monkeypatch.setattr(
        open_telemetry, "OTLPSpanExporter", MagicMock(return_value=exporter)
    )
    monkeypatch.setattr(
        open_telemetry, "BatchSpanProcessor", MagicMock(return_value=processor)
    )
    monkeypatch.setattr(open_telemetry.otel_trace, "set_tracer_provider", MagicMock())
    monkeypatch.setattr(open_telemetry, "RedisInstrumentor", MagicMock())
    monkeypatch.setattr(open_telemetry, "HTTPXClientInstrumentor", MagicMock())
    monkeypatch.setattr(open_telemetry, "FastAPIInstrumentor", MagicMock())

    app = MagicMock()
    assert open_telemetry.init_tracing(app=app) is provider

    open_telemetry.OTLPSpanExporter.assert_called_once_with(
        endpoint="http://collector:4317"
    )
    open_telemetry.BatchSpanProcessor.assert_called_once_with(exporter)
    provider.add_span_processor.assert_called_once_with(processor)
    open_telemetry.otel_trace.set_tracer_provider.assert_called_once_with(provider)
    open_telemetry.FastAPIInstrumentor.instrument_app.assert_called_once_with(app)
