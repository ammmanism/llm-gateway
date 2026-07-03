"""
OpenTelemetry Tracing
"""

import logging
from fastapi import FastAPI

logger = logging.getLogger(__name__)

def setup_tracing(app: FastAPI):
    """Setup OpenTelemetry instrumentation."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Setup tracer provider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

        # Setup Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name="jaeger",
            agent_port=6831,
        )
        span_processor = BatchSpanProcessor(jaeger_exporter)
        provider.add_span_processor(span_processor)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing enabled")
    except ImportError:
        logger.warning("OpenTelemetry not installed, tracing disabled")
    except Exception as e:
        logger.warning(f"Failed to setup tracing: {e}")
