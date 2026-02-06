"""
OpenTelemetry configuration for distributed tracing.
"""

import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor

def setup_tracing(app, service_name="strands-api"):
    """
    Configure OpenTelemetry tracing for the application.
    
    Args:
        app: FastAPI application instance
        service_name: Name of the service for tracing
    """
    # Check if tracing is enabled
    if os.getenv("ENABLE_TRACING", "false").lower() != "true":
        return

    # Configure resource
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("APP_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "production")
    })

    # Configure provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporter (OTLP gRPC)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    
    # Configure processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    # Set global provider
    trace.set_tracer_provider(provider)
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    
    # Instrument Requests (for external API calls)
    RequestsInstrumentor().instrument()
    
    # Instrument AsyncIO
    AsyncioInstrumentor().instrument()
    
    return provider
