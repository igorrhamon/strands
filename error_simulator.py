"""
Error Simulator - Generates random errors and metrics for testing observability.
"""

import asyncio
import random
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Error Simulator")

# Configure OpenTelemetry
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://jaeger:14250", insecure=True)
    )
)
FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer(__name__)

# Define custom metrics
error_counter = Counter(
    'simulator_errors_total',
    'Total number of simulated errors',
    ['error_type', 'severity']
)

request_duration = Histogram(
    'simulator_request_duration_seconds',
    'Request processing duration',
    ['endpoint', 'status']
)

active_errors = Gauge(
    'simulator_active_errors',
    'Number of currently active errors'
)

error_rate = Gauge(
    'simulator_error_rate_percent',
    'Current error rate percentage'
)

# Simulated error types
ERROR_TYPES = [
    'database_timeout',
    'network_error',
    'memory_leak',
    'cpu_spike',
    'disk_full',
    'auth_failure',
    'service_unavailable'
]

SEVERITIES = ['low', 'medium', 'high', 'critical']

class ErrorSimulator:
    def __init__(self):
        self.active_errors = []
        self.total_requests = 0
        self.failed_requests = 0
        
    async def generate_error(self):
        """Generate a random error."""
        error_type = random.choice(ERROR_TYPES)
        severity = random.choice(SEVERITIES)
        
        error = {
            'type': error_type,
            'severity': severity,
            'timestamp': time.time(),
            'duration': random.uniform(1, 30)
        }
        
        self.active_errors.append(error)
        error_counter.labels(error_type=error_type, severity=severity).inc()
        active_errors.set(len(self.active_errors))
        
        logger.warning(f"Generated error: {error_type} ({severity})")
        
        # Simulate error duration
        await asyncio.sleep(error['duration'])
        
        if error in self.active_errors:
            self.active_errors.remove(error)
            active_errors.set(len(self.active_errors))
            
    async def error_generator_loop(self):
        """Continuously generate errors."""
        while True:
            # Generate error with 30% probability
            if random.random() < 0.3:
                await self.generate_error()
            
            # Update error rate
            if self.total_requests > 0:
                rate = (self.failed_requests / self.total_requests) * 100
                error_rate.set(rate)
            
            await asyncio.sleep(random.uniform(2, 8))

simulator = ErrorSimulator()

@app.on_event("startup")
async def startup_event():
    """Start error generation loop."""
    asyncio.create_task(simulator.error_generator_loop())
    logger.info("Error simulator started")

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "active_errors": len(simulator.active_errors)}

@app.get("/simulate/{error_type}")
async def simulate_error(error_type: str):
    """Manually trigger a specific error type."""
    start_time = time.time()
    
    with tracer.start_as_current_span(f"simulate_{error_type}") as span:
        span.set_attribute("error_type", error_type)
        
        try:
            simulator.total_requests += 1
            
            if error_type not in ERROR_TYPES:
                raise HTTPException(status_code=400, detail=f"Unknown error type: {error_type}")
            
            # Simulate processing
            await asyncio.sleep(random.uniform(0.1, 2.0))
            
            # Always record the error in metrics
            simulator.failed_requests += 1
            severity = random.choice(SEVERITIES)
            error_counter.labels(error_type=error_type, severity=severity).inc()
            
            duration = time.time() - start_time
            request_duration.labels(endpoint="/simulate", status="success").observe(duration)
            
            return {
                "error_type": error_type,
                "status": "simulated",
                "duration": duration,
                "active_errors": len(simulator.active_errors)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/errors")
async def get_errors():
    """Get current active errors."""
    return {
        "active_errors": len(simulator.active_errors),
        "total_requests": simulator.total_requests,
        "failed_requests": simulator.failed_requests,
        "error_rate_percent": (simulator.failed_requests / simulator.total_requests * 100) if simulator.total_requests > 0 else 0,
        "errors": simulator.active_errors
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
