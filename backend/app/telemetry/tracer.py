"""
OpenTelemetry Tracing Integration with Jaeger / OTLP support.
Gracefully degrades to no-op if OTLP collector is unreachable or not configured.
"""

import os
import logging
from contextlib import contextmanager

logger = logging.getLogger("preauth.telemetry.tracer")

_tracer = None

def init_tracer(service_name: str = "preauth-desk"):
    global _tracer
    if _tracer is not None:
        return _tracer

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318/v1/traces")
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        # Attempt to attach OTLP exporter if exporter package is installed
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("Configured OTLP Span Exporter targeting %s", otlp_endpoint)
        except Exception as e:
            logger.warning("OTLP HTTP exporter not configured or failed to initialize (%s). Falling back to provider with no exporter.", e)

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
    except Exception as e:
        logger.warning("Failed to initialize OpenTelemetry SDK: %s. Using No-op tracer.", e)
        _tracer = NoOpTracer()

    return _tracer


class NoOpSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, key, value):
        pass

    def record_exception(self, exception):
        pass

    def set_status(self, status, description=None):
        pass


class NoOpTracer:
    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield NoOpSpan()


def get_tracer(service_name: str = "preauth-desk"):
    global _tracer
    if _tracer is None:
        return init_tracer(service_name)
    return _tracer
