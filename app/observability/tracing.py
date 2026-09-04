from __future__ import annotations

from app.config import AppConfig


def setup_tracing(config: AppConfig) -> None:
    if not config.otel_enabled:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )

    provider = TracerProvider(
        resource=Resource.create({"service.name": config.otel_service_name})
    )
    if config.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=config.otel_exporter_otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def get_tracer(name: str):
    from opentelemetry import trace

    return trace.get_tracer(name)
