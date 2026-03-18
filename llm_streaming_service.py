"""
LLM Streaming Service with OpenTelemetry Metrics (TTFT & TPS)

This module provides an LLM service that:
1. Receives tokens in SSE (Server-Sent Events) format
2. Calculates TTFT (Time to First Token) 
3. Calculates TPS (Tokens Per Second)
4. Reports metrics to OpenTelemetry
"""

import time
import typing
from dataclasses import dataclass

from opentelemetry import trace, metrics
from opentelemetry.trace import Tracer
from opentelemetry.metrics import Meter


@dataclass
class TokenStreamMetrics:
    """Container for streaming metrics."""
    ttft_ms: float  # Time to First Token in milliseconds
    tps: float     # Tokens Per Second
    total_tokens: int
    total_duration_s: float
    full_response: str


class LLMStreamingService:
    """
    OpenTelemetry-instrumented LLM service that handles token streaming.
    
    Attributes:
        tracer: OpenTelemetry Tracer instance
        meter: OpenTelemetry Meter instance
    """

    def __init__(self, service_name: str = "llm-service", model_name: str = "gpt-4-streaming"):
        self.service_name = service_name
        self.model_name = model_name
        self.tracer: Tracer = trace.get_tracer(service_name)
        self.meter: Meter = metrics.get_meter(service_name)
        
        # Create metric instruments
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Initialize OTEL metric instruments."""
        # Histogram for Time to First Token (milliseconds)
        self.ttft_histogram = self.meter.create_histogram(
            name="llm.ttft",
            description="Time to First Token in milliseconds",
            unit="ms",
        )

        # Histogram for Tokens Per Second throughput
        self.tps_histogram = self.meter.create_histogram(
            name="llm.tokens_per_second",
            description="Tokens per second throughput",
            unit="tokens/s",
        )

        # Counter for total tokens generated
        self.token_counter = self.meter.create_counter(
            name="llm.tokens_generated",
            description="Total number of tokens generated",
            unit="1",
        )

        # Gauge for last request TTFT
        self.ttft_gauge = self.meter.create_gauge(
            name="llm.ttft_last",
            description="Last recorded TTFT",
            unit="ms",
        )

    def stream_tokens(
        self,
        token_generator: typing.Generator[str, None, None],
    ) -> TokenStreamMetrics:
        """
        Process a stream of tokens and calculate metrics.

        Args:
            token_generator: Generator yielding tokens one at a time

        Returns:
            TokenStreamMetrics with TTFT, TPS, and other stats
        """
        request_start_time = time.time()
        first_token_time: typing.Optional[float] = None
        total_tokens = 0
        full_response = ""
        ttft_ms: float = 0.0

        # Collect tokens and track timing
        for token in token_generator:
            if first_token_time is None:
                first_token_time = time.time()
                ttft_ms = (first_token_time - request_start_time) * 1000

            full_response += token
            total_tokens += 1

        # Calculate final metrics
        completion_time = time.time()
        total_duration_seconds = completion_time - request_start_time
        tps = total_tokens / total_duration_seconds if total_duration_seconds > 0 else 0

        metrics_obj = TokenStreamMetrics(
            ttft_ms=ttft_ms,
            tps=tps,
            total_tokens=total_tokens,
            total_duration_s=total_duration_seconds,
            full_response=full_response,
        )

        return metrics_obj

    def process_request(
        self,
        prompt: str,
        token_generator: typing.Generator[str, None, None],
        session_id: str = "",
        parent_context = None,
    ) -> TokenStreamMetrics:
        """
        Process an LLM request with streaming tokens and record metrics.

        Args:
            prompt: The user prompt/request
            token_generator: Generator yielding tokens one at a time
            session_id: Optional session ID for correlation
            parent_context: Optional parent trace context for context propagation

        Returns:
            TokenStreamMetrics with TTFT, TPS, and response
        """
        ctx = parent_context if parent_context is not None else None

        with self.tracer.start_as_current_span(
            "llm.generate_streaming",
            context=ctx,
        ) as span:
            # Set span attributes
            span.set_attribute("llm.service", self.service_name)
            span.set_attribute("llm.model", self.model_name)
            span.set_attribute("llm.prompt", prompt)
            span.set_attribute("llm.streaming", True)
            if session_id:
                span.set_attribute("session.id", session_id)

            # Process token stream and collect metrics
            metrics_obj = self.stream_tokens(token_generator)

            # Record metrics to OpenTelemetry
            metric_attributes = {
                "llm.model": self.model_name,
                "llm.service": self.service_name,
            }
            if session_id:
                metric_attributes["session.id"] = session_id

            self.ttft_histogram.record(metrics_obj.ttft_ms, metric_attributes)
            self.tps_histogram.record(metrics_obj.tps, metric_attributes)
            self.token_counter.add(metrics_obj.total_tokens, metric_attributes)
            self.ttft_gauge.callback(lambda: [metrics_obj.ttft_ms])

            # Set span attributes with metrics
            span.set_attribute("llm.ttft_ms", round(metrics_obj.ttft_ms, 2))
            span.set_attribute("llm.tps", round(metrics_obj.tps, 2))
            span.set_attribute("llm.tokens_generated", metrics_obj.total_tokens)
            span.set_attribute("llm.total_duration_ms", round(metrics_obj.total_duration_s * 1000, 1))
            span.set_attribute("llm.response_length", len(metrics_obj.full_response))
            span.set_status(trace.Status(trace.StatusCode.OK))

            return metrics_obj

    def log_metrics(self, metrics_obj: TokenStreamMetrics, prefix: str = "") -> None:
        """
        Pretty-print metrics to console.

        Args:
            metrics_obj: TokenStreamMetrics object
            prefix: Optional prefix for output lines
        """
        print(f"{prefix}  ✓ TTFT: {metrics_obj.ttft_ms:.1f}ms")
        print(f"{prefix}  ✓ TPS: {metrics_obj.tps:.2f} tokens/s")
        print(f"{prefix}  ✓ Total Tokens: {metrics_obj.total_tokens}")
        print(f"{prefix}  ✓ Duration: {metrics_obj.total_duration_s:.2f}s")
        print(f"{prefix}  ✓ Response Length: {len(metrics_obj.full_response)} chars")
