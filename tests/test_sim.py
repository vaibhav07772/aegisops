from sim.config import SERVICE_NAMES
from sim.generator import TelemetryGenerator
from sim.models import IncidentScenario


def test_normal_tick_produces_telemetry():
    gen = TelemetryGenerator(IncidentScenario.NORMAL, seed=42)
    metrics, logs, spans = gen.tick(progress=0.0)
    assert len(metrics) == len(SERVICE_NAMES) * 5
    assert len(spans) > 0


def test_service_outage_raises_payment_error_rate():
    gen = TelemetryGenerator(IncidentScenario.SERVICE_OUTAGE, seed=42)
    metrics, _, _ = gen.tick(progress=1.0)
    payment_err = [
        m.value for m in metrics
        if m.service == "payment-service" and m.metric_name == "error_rate"
    ]
    assert payment_err and payment_err[0] > 0.5


def test_memory_leak_grows_over_time():
    gen = TelemetryGenerator(IncidentScenario.MEMORY_LEAK, seed=42)
    start_m, _, _ = gen.tick(progress=0.05)
    end_m, _, _ = gen.tick(progress=0.95)
    s = [m.value for m in start_m if m.service == "order-service" and m.metric_name == "memory_mb"]
    e = [m.value for m in end_m if m.service == "order-service" and m.metric_name == "memory_mb"]
    assert e[0] > s[0]


def test_error_cascade_raises_auth_error_rate():
    gen = TelemetryGenerator(IncidentScenario.ERROR_CASCADE, seed=42)
    metrics, _, _ = gen.tick(progress=0.8)
    auth_err = [
        m.value for m in metrics
        if m.service == "auth-service" and m.metric_name == "error_rate"
    ]
    assert auth_err and auth_err[0] > 0.3