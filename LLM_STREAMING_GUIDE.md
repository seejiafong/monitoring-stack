# LLM Streaming Service with OTEL Metrics (TTFT & TPS)

This guide explains how to instrument an LLM service that receives tokens in Server-Sent Events (SSE) format to calculate and report **TTFT** (Time to First Token) and **TPS** (Tokens Per Second) as OpenTelemetry metrics.

---

## Concepts

### TTFT (Time to First Token)
- **Definition**: The time elapsed from when a request is sent until the first token is received
- **Unit**: Milliseconds (ms)
- **Why it matters**: Indicates the initial latency/responsiveness of the LLM API
- **Typical range**: 50-500ms depending on model and load

**Calculation**:
```
TTFT = first_token_received_time - request_sent_time
```

### TPS (Tokens Per Second)
- **Definition**: The rate at which tokens are generated and streamed
- **Unit**: Tokens per second (tokens/s)
- **Why it matters**: Indicates the throughput/speed of token generation
- **Typical range**: 10-100 tokens/s depending on model hardware

**Calculation**:
```
TPS = total_tokens_received / total_time_seconds
```

---

## Architecture

The solution consists of three components:

### 1. **llm_streaming_service.py** - Core Service
- `LLMStreamingService` class: Handles token streaming and metric collection
- `TokenStreamMetrics` dataclass: Container for TTFT, TPS, token count, etc.
- Methods:
  - `stream_tokens()`: Core token processing loop
  - `process_request()`: Full request handling with tracing
  - `log_metrics()`: Pretty-print metrics

### 2. **otel_simulation.ipynb** - Jupyter Notebook Demo
- Sets up OTEL tracer and meter providers
- Simulates SSE token streaming
- Demonstrates multi-service traces with metrics
- Shows batch processing of multiple requests

### 3. **example_llm_streaming.py** - Standalone Example
- Shows how to integrate in production code
- Demonstrates both single and batch request processing
- Includes token generator simulation
- Shows metrics aggregation

---

## Implementation Details

### Token Processing Loop

```python
for token in token_generator:
    if first_token_time is None:
        # Record when first token arrived
        first_token_time = time.time()
        ttft_ms = (first_token_time - request_start_time) * 1000
    
    # Accumulate tokens
    full_response += token
    total_tokens += 1

# Calculate TPS after all tokens received
tps = total_tokens / (completion_time - request_start_time)
```

### OTEL Metric Types Used

1. **Histogram (TTFT & TPS)**
   - Automatically calculates percentiles (P50, P95, P99)
   - Records min/max/count distribution
   - Useful for understanding variation

2. **Counter (Token Count)**
   - Monotonically increasing counter
   - Total tokens generated across all requests
   - Useful for throughput analysis

3. **Gauge (Last TTFT)**
   - Current/last recorded value
   - Updates with each request
   - Useful for real-time monitoring

### Span Attributes

The service records these span attributes for detailed tracing:
- `llm.ttft_ms`: Time to first token
- `llm.tps`: Tokens per second
- `llm.tokens_generated`: Total token count
- `llm.total_duration_ms`: Total request duration
- `llm.prompt`: The user's prompt
- `llm.model`: Model name
- `session.id`: Session correlation ID

---

## Usage Examples

### Example 1: Using the Jupyter Notebook

1. **Prerequisites**:
   ```bash
   uv add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
   ```

2. **Select the kernel**: In Jupyter, select `otel-experiment`

3. **Run cells in order**:
   - Cell 1: Configure tracer and metrics providers
   - Cell 2: Define streaming LLM service
   - Cell 3: Test single streaming request
   - Cell 4: Run multiple streaming sessions

### Example 2: Using the Standalone Module

```python
from llm_streaming_service import LLMStreamingService
import time
from typing import Generator

# Initialize service
service = LLMStreamingService(model_name="gpt-4")

# Define a token generator (from SSE, API, etc.)
def token_stream() -> Generator[str, None, None]:
    time.sleep(0.1)  # Initial delay
    for word in ["Hello", "world", "from", "LLM"]:
        yield word + " "
        time.sleep(0.02)  # Inter-token delay

# Process request
metrics = service.process_request(
    prompt="Say hello",
    token_generator=token_stream(),
    session_id="my-session-123"
)

# Access metrics
print(f"TTFT: {metrics.ttft_ms:.1f}ms")
print(f"TPS: {metrics.tps:.2f} tokens/s")
print(f"Total tokens: {metrics.total_tokens}")
```

### Example 3: Integrating with Real LLM API (OpenAI, Claude, etc.)

```python
import anthropic
from llm_streaming_service import LLMStreamingService

service = LLMStreamingService(model_name="claude-3-sonnet")

def claude_token_stream():
    """Generator from Anthropic SDK"""
    with anthropic.Anthropic().messages.stream(
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello!"}],
        model="claude-3-sonnet-20240229",
    ) as stream:
        for text in stream.text_stream:
            yield text

metrics = service.process_request(
    prompt="Hello!",
    token_generator=claude_token_stream(),
    session_id="production-123"
)

service.log_metrics(metrics)
```

---

## Viewing Metrics in Jaeger

Once metrics are exported to OpenTelemetry Collector → Jaeger:

### 1. Find Your Trace
- In Jaeger UI (http://localhost:16686)
- Filter by `session.id=<your-session-uuid>`
- Click on the trace to view spans

### 2. View Metrics in Span Attributes
- Click on `llm-service.generate_streaming` span
- Scroll to "Attributes" section
- Look for:
  - `llm.ttft_ms` - Time to first token
  - `llm.tps` - Tokens per second
  - `llm.tokens_generated` - Token count
  - `llm.total_duration_ms` - Total time

### 3. Check Prometheus Metrics
If Prometheus is configured:
- Query `llm_ttft` for TTFT distribution
- Query `llm_tokens_per_second` for TPS distribution
- Query `sum(rate(llm_tokens_generated[1m]))` for throughput

---

## Docker Setup

To run the complete stack locally:

```bash
# Terminal 1: Jaeger (UI) + Collector
docker-compose up

# Terminal 2: Your notebook or Python script
python example_llm_streaming.py
```

### docker-compose.yml Example
```yaml
version: '3'
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "14250:14250"  # gRPC receiver
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4317:4317"  # gRPC receiver
    volumes:
      - ./otel-collector-config.yml:/etc/otel-collector-config.yml
    command: ["--config=/etc/otel-collector-config.yml"]
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:14250
```

---

## Metrics Export Formats

### OpenTelemetry Format (OTLP/gRPC)
```
Resource: service.name=llm-demo
Histogram llm.ttft:
  - Attributes: llm.model=gpt-4, session.id=abc-123
  - Value: 125.5ms (per request)

Histogram llm.tokens_per_second:
  - Attributes: llm.model=gpt-4, session.id=abc-123
  - Value: 45.2 tokens/s

Counter llm.tokens_generated:
  - Attributes: llm.model=gpt-4, session.id=abc-123
  - Value: 2847 (cumulative)
```

### Prometheus Format
```
# Histograms (automatically converted)
llm_ttft_bucket{llm_model="gpt-4",le="50"} 0
llm_ttft_bucket{llm_model="gpt-4",le="100"} 3
llm_ttft_bucket{llm_model="gpt-4",le="500"} 10
llm_ttft_sum{llm_model="gpt-4"} 1250
llm_ttft_count{llm_model="gpt-4"} 10

# Counters
llm_tokens_generated_total{llm_model="gpt-4"} 28470
```

---

## Troubleshooting

### Metrics not appearing?
1. Check collector is running: `curl http://localhost:4317/v1/metrics`
2. Verify `COLLECTOR_ENDPOINT` is correct in code
3. Ensure `metric_provider.force_flush()` is called before shutdown
4. Check collector logs for export errors

### Incorrect TTFT values?
1. Ensure `request_start_time` is captured **before** generator is created
2. Verify token generator includes initial delay
3. Check system clock synchronization

### Low TPS readings?
1. Check inter-token delays in token generator
2. Verify network latency isn't dominating
3. Use profiler to identify bottlenecks

---

## Performance Tips

1. **Batch Metrics**: Increase batch size in `PeriodicExportingMetricReader()`
2. **Buffer Tokens**: Process large responses in chunks rather than character by character
3. **Filter Attributes**: Remove unnecessary attributes from metrics to reduce cardinality
4. **Sampling**: Use sampling for very high-frequency requests

---

## References

- [OpenTelemetry Metrics API](https://opentelemetry.io/docs/instrumentation/python/manual/#metrics)
- [OTEL Histogram Instruments](https://opentelemetry.io/docs/reference/specification/metrics/data-model/#histogram)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)

---

**Created**: 2026-03-04  
**Updated**: Updated to include SSE streaming and metric collection examples
