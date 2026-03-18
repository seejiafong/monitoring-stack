"""
Example: Using LLMStreamingService with OTEL Metrics

This example demonstrates how to:
1. Set up OpenTelemetry tracing and metrics
2. Use the LLMStreamingService to process token streams
3. Record TTFT and TPS metrics automatically
"""

import time
import uuid
from typing import Generator

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

from llm_streaming_service import LLMStreamingService


# ═════════════════════════════════════════════════════════════════════════════
# OTEL Setup
# ═════════════════════════════════════════════════════════════════════════════

COLLECTOR_ENDPOINT = "http://localhost:4317"
INSECURE = True

# Create resource
resource = Resource.create({
    "service.name": "llm-demo",
    "deployment.environment": "demo",
})

# Setup trace exporter
otlp_trace_exporter = OTLPSpanExporter(
    endpoint=COLLECTOR_ENDPOINT,
    insecure=INSECURE,
)
trace_provider = TracerProvider(resource=resource)
trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(trace_provider)

# Setup metrics exporter
otlp_metric_exporter = OTLPMetricExporter(
    endpoint=COLLECTOR_ENDPOINT,
    insecure=INSECURE,
)
metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(metric_provider)

print("✓ OpenTelemetry configured (Tracer & Metrics)")


# ═════════════════════════════════════════════════════════════════════════════
# Example Token Stream Generator (simulate SSE from LLM API)
# ═════════════════════════════════════════════════════════════════════════════

def simulate_llm_stream(prompt: str) -> Generator[str, None, None]:
    """Simulate receiving tokens from an LLM API in SSE format."""
    # Simulate initial delay before first token
    time.sleep(0.08)
    
    # Simulate an actual LLM response
    sample_responses = {
        "explain": [
            "OpenTelemetry", " is", " a", " framework", " for", " collecting",
            " traces", ",", " metrics", ",", " and", " logs", " from", " your", " applications",
            ".", " It", " provides", " standardized", " instrumentation", "."
        ],
        "compare": [
            "TTFT", " (", "Time", " to", " First", " Token", ")", " measures",
            " latency", " to", " the", " first", " token", ".", " TPS",
            " (", "Tokens", " per", " Second", ")", " measures", " throughput", "."
        ],
    }
    
    key = "explain" if "explain" in prompt.lower() else "compare"
    tokens = sample_responses.get(key, ["Response", " token"])
    
    for token in tokens:
        yield token
        time.sleep(0.02)  # Inter-token delay


# ═════════════════════════════════════════════════════════════════════════════
# Example Usage
# ═════════════════════════════════════════════════════════════════════════════

def main():
    # Create service
    service = LLMStreamingService(
        service_name="llm-demo",
        model_name="gpt-4-turbo"
    )
    
    # Example 1: Single request
    print("\n" + "=" * 70)
    print("Example 1: Single LLM Request with Streaming")
    print("=" * 70)
    
    session_id = str(uuid.uuid4())
    prompt = "Explain OpenTelemetry in one sentence."
    
    print(f"Session: {session_id}")
    print(f"Prompt:  {prompt}")
    print("-" * 70)
    
    # Generate token stream
    token_stream = simulate_llm_stream(prompt)
    
    # Process with metrics collection
    metrics_obj = service.process_request(
        prompt=prompt,
        token_generator=token_stream,
        session_id=session_id,
    )
    
    print("\nMetrics:")
    service.log_metrics(metrics_obj, prefix="")
    print(f"\nResponse: {metrics_obj.full_response}")
    
    
    # Example 2: Multiple requests (batch processing)
    print("\n" + "=" * 70)
    print("Example 2: Multiple Requests with Metrics Aggregation")
    print("=" * 70)
    
    prompts = [
        "Explain OpenTelemetry in one sentence.",
        "Compare TTFT and TPS metrics.",
    ]
    
    all_metrics = []
    for i, prompt in enumerate(prompts, 1):
        session_id = str(uuid.uuid4())
        print(f"\nRequest {i}: {prompt}")
        print("-" * 70)
        
        token_stream = simulate_llm_stream(prompt)
        metrics_obj = service.process_request(
            prompt=prompt,
            token_generator=token_stream,
            session_id=session_id,
        )
        
        all_metrics.append(metrics_obj)
        service.log_metrics(metrics_obj, prefix="")
    
    # Print aggregate statistics
    print("\n" + "=" * 70)
    print("Aggregate Metrics across all requests")
    print("=" * 70)
    
    avg_ttft = sum(m.ttft_ms for m in all_metrics) / len(all_metrics)
    avg_tps = sum(m.tps for m in all_metrics) / len(all_metrics)
    total_tokens = sum(m.total_tokens for m in all_metrics)
    
    print(f"Average TTFT:  {avg_ttft:.1f}ms")
    print(f"Average TPS:   {avg_tps:.2f} tokens/s")
    print(f"Total Tokens:  {total_tokens}")
    print(f"Total Requests: {len(all_metrics)}")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Flush and shutdown
        trace_provider.force_flush(timeout_millis=5000)
        trace_provider.shutdown()
        
        if hasattr(metric_provider, 'force_flush'):
            metric_provider.force_flush(timeout_millis=5000)
        if hasattr(metric_provider, 'shutdown'):
            metric_provider.shutdown()
        
        print("\n✓ All metrics and traces flushed to OpenTelemetry Collector")
