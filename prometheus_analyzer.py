"""
Prometheus Analyzer Service
Analisa métricas do Prometheus e gera insights usando LLM (Ollama)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import importlib
import os
import json
import uvicorn

# Constants
AIOHTTP_MISSING = "aiohttp is required but not installed"


def _get_aiohttp():
    try:
        return importlib.import_module("aiohttp")
    except Exception:
        return None


def _get_fastapi():
    try:
        return importlib.import_module("fastapi")
    except Exception:
        return None


# Provide a lightweight FastAPI stub when module is not present so decorators
# still work for static analysis or non-runtime inspection.
_fastapi_mod = _get_fastapi()
if _fastapi_mod is not None:
    FastAPI = _fastapi_mod.FastAPI
else:
    class FastAPI:  # lightweight stub
        def __init__(self, *args, **kwargs):
            # stub implementation used when FastAPI isn't installed; decorators only need a callable
            pass

        def on_event(self, event: str):
            def decorator(fn):
                return fn

            return decorator

        def get(self, path: str):
            # path parameter is ignored in the stub; keep signature compatible with FastAPI
            def decorator(fn):
                return fn

            return decorator

        def post(self, path: str):
            # path parameter is ignored in the stub; keep signature compatible with FastAPI
            def decorator(fn):
                return fn

            return decorator


# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("prometheus-analyzer")

# Configuration
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
ANALYSIS_INTERVAL = int(os.getenv("ANALYSIS_INTERVAL", "60"))  # Seconds


class PrometheusAnalyzer:
    """Analisa métricas do Prometheus e gera insights com LLM"""

    def __init__(self, prometheus_url: str, ollama_url: str):
        self.prometheus_url = prometheus_url
        self.ollama_url = ollama_url
        self.session: Optional[Any] = None
        self.last_analysis = {}

    async def init(self):
        """Inicializar sessão HTTP"""
        aiohttp_mod = _get_aiohttp()
        if aiohttp_mod is None:
            raise RuntimeError(AIOHTTP_MISSING)
        self.session = aiohttp_mod.ClientSession()

    async def close(self):
        """Fechar sessão HTTP"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _ensure_session(self):
        """Ensure there's an active aiohttp session (create lazily)."""
        aiohttp_mod = _get_aiohttp()
        if aiohttp_mod is None:
            raise RuntimeError(AIOHTTP_MISSING)

        if self.session is None or getattr(self.session, "closed", True):
            self.session = aiohttp_mod.ClientSession()

    async def query_prometheus(self, query: str) -> Dict:
        """Executar query no Prometheus"""
        try:
            await self._ensure_session()
            aiohttp_mod = _get_aiohttp()
            session = self.session
            if session is None:
                logger.error("No HTTP session available for Prometheus query")
                return {"status": "error", "error": "no_session"}

            url = f"{self.prometheus_url}/api/v1/query"
            params = {"query": query}

            if aiohttp_mod is None:
                raise RuntimeError(AIOHTTP_MISSING)

            async with session.get(url, params=params, timeout=aiohttp_mod.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Prometheus error: {resp.status}")
                    return {"status": "error", "http_status": resp.status}
        except Exception as e:
            logger.error(f"Query error: {e}")
            return {"status": "error", "error": str(e)}

    async def get_metrics_summary(self) -> Dict:
        """Obter resumo das métricas principais"""
        metrics = {}

        # Queries importantes
        queries = {
            "error_rate": "rate(http_requests_total{status=~'5..'}[5m])",
            "request_latency_p95": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "cpu_usage": "rate(process_cpu_seconds_total[5m]) * 100",
            "memory_usage": "process_resident_memory_bytes / 1024 / 1024",
            "active_connections": "up",
            "error_simulator_errors": "simulator_errors_total",
        }

        for metric_name, query in queries.items():
            try:
                result = await self.query_prometheus(query)
                if result.get("status") == "success":
                    data = result.get("data", {}).get("result", [])
                    if data:
                        metrics[metric_name] = {
                            "value": data[0].get("value", [None, None])[1],
                            "timestamp": datetime.now().isoformat(),
                            "labels": data[0].get("metric", {})
                        }
                    else:
                        metrics[metric_name] = {"value": None, "error": "No data"}
                else:
                    metrics[metric_name] = {"value": None, "error": "Query failed"}
            except Exception as e:
                logger.error(f"Error querying {metric_name}: {e}")
                metrics[metric_name] = {"value": None, "error": str(e)}

        return metrics

    async def analyze_with_llm(self, metrics_summary: Dict) -> Dict:
        """Usar LLM para analisar métricas e gerar insights"""
        try:
            await self._ensure_session()
            aiohttp_mod = _get_aiohttp()
            session = self.session
            if session is None:
                logger.error("No HTTP session available for LLM call")
                return {"status": "error", "error": "no_session"}

            # Preparar prompt com métricas
            prompt = self._prepare_analysis_prompt(metrics_summary)

            # Chamar Ollama
            url = f"{self.ollama_url}/api/generate"

            # Models: primary plus optional fallbacks (comma-separated env var)
            primary_model = os.getenv("OLLAMA_MODEL", "ministral-3:3b")
            fallback_env = os.getenv("OLLAMA_FALLBACK_MODELS", "")
            fallback_models = [m.strip() for m in fallback_env.split(",") if m.strip()]
            models_to_try = [primary_model] + [m for m in fallback_models if m != primary_model]

            # Configuráveis via ambiente
            # Increase defaults: more retries and longer timeout to accommodate slow model responses
            retries = int(os.getenv("OLLAMA_RETRIES", "4"))
            timeout_sec = int(os.getenv("OLLAMA_TIMEOUT", "3000"))

            if aiohttp_mod is None:
                raise RuntimeError(AIOHTTP_MISSING)

            overall_last_error = None

            for model_name in models_to_try:
                # Enable streaming to receive partial results and avoid client-side timeouts
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": True,
                    "temperature": 0.7,
                }

                logger.info(f"Calling LLM with model '{model_name}' at {url}")

                last_error = None
                for attempt in range(1, retries + 1):
                    try:
                        async with session.post(url, json=payload, timeout=aiohttp_mod.ClientTimeout(total=timeout_sec)) as resp:
                            if resp.status != 200:
                                # Try to capture body for diagnostics
                                try:
                                    body_text = await resp.text()
                                except Exception:
                                    body_text = None
                                last_error = f"http_{resp.status}"
                                logger.error(f"LLM request failed - HTTP {resp.status} (attempt {attempt}/{retries}, model: {model_name})")
                                break  # don't retry on HTTP error

                            # If streaming, consume chunks as they arrive
                            if payload.get("stream"):
                                accumulated = ""
                                streaming_error = None
                                try:
                                    async for chunk in resp.content.iter_chunked(1024):
                                        try:
                                            text = chunk.decode(errors="ignore")
                                        except Exception:
                                            text = str(chunk)
                                        accumulated += text
                                        # optional: could yield partial results or log progress here
                                except asyncio.CancelledError:
                                    raise
                                except Exception as e:
                                    streaming_error = str(e)
                                    logger.warning(f"Error while streaming LLM response: {streaming_error} (accumulated: {len(accumulated)} bytes, model: {model_name})")

                                # Try to parse accumulated JSON if possible, otherwise return raw text
                                if accumulated:
                                    try:
                                        parsed = json.loads(accumulated)
                                        raw = parsed
                                        analysis_text = (
                                            parsed.get("response")
                                            or parsed.get("text")
                                            or parsed.get("output")
                                            or ("\n".join(c.get("text", "") for c in parsed.get("choices", [])) if parsed.get("choices") else None)
                                        ) or ""
                                        return {"status": "success", "analysis": analysis_text, "timestamp": datetime.now().isoformat(), "raw": raw, "model": model_name}
                                    except Exception:
                                        # Return the accumulated text as-is if JSON parsing fails
                                        return {"status": "success", "analysis": accumulated, "timestamp": datetime.now().isoformat(), "model": model_name}
                                else:
                                    # If nothing was accumulated, log error and try non-streaming fallback
                                    logger.error(f"No data accumulated during streaming: {streaming_error} (model: {model_name})")

                            # Non-streaming fallback (should be rare with stream enabled)
                            body_text = None
                            try:
                                body_text = await resp.text()
                            except Exception:
                                body_text = None
                            try:
                                result = json.loads(body_text) if body_text else {}
                            except Exception:
                                logger.warning(f"LLM returned non-JSON - attempt {attempt}/{retries} (model: {model_name})")
                                return {"status": "success", "analysis": body_text or "", "timestamp": datetime.now().isoformat(), "model": model_name}

                            analysis_text = ""
                            if isinstance(result, dict):
                                analysis_text = (
                                    result.get("response")
                                    or result.get("text")
                                    or result.get("output")
                                    or ("\n".join(c.get("text", "") for c in result.get("choices", [])) if result.get("choices") else None)
                                ) or ""
                            else:
                                analysis_text = str(result)

                            return {"status": "success", "analysis": analysis_text, "timestamp": datetime.now().isoformat(), "raw": result, "model": model_name}

                    except asyncio.TimeoutError:
                        last_error = "timeout"
                        logger.warning(f"Timeout when calling LLM - {timeout_sec}s exceeded (attempt {attempt}/{retries}, model: {model_name})")
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"Error when calling LLM - {last_error} (attempt {attempt}/{retries}, model: {model_name})")

                    if attempt < retries:
                        backoff = 2 ** (attempt - 1)
                        await asyncio.sleep(backoff)

                overall_last_error = last_error
                logger.info(f"Model attempt finished (model: {model_name}, last_error: {last_error})")
                # try next model if available

            # All models and retries exhausted
            logger.error(f"All models exhausted for LLM call - last error: {overall_last_error} (models tried: {models_to_try})")
            return {"status": "error", "error": "ollama_all_models_failed", "detail": overall_last_error, "models_tried": models_to_try}

        except Exception:
            logger.exception("LLM analysis error")
            import traceback

            tb = traceback.format_exc()
            return {"status": "error", "error": "exception during LLM analysis", "traceback": tb}

    def _prepare_analysis_prompt(self, metrics: Dict) -> str:
        """Preparar prompt para LLM com métricas"""
        metrics_text = json.dumps(metrics, indent=2)

        prompt = f"""Você é um especialista em observabilidade e análise de sistemas distribuídos.

Analise as seguintes métricas do Prometheus e forneça insights acionáveis:

MÉTRICAS COLETADAS:
{metrics_text}

Por favor, forneça:
1. Resumo do status atual do sistema
2. Alertas ou anomalias detectadas
3. Recomendações de ações
4. Tendências observadas

Seja conciso e técnico. Foque em problemas críticos primeiro."""

        return prompt

    async def check_alerts(self, metrics: Dict) -> List[Dict]:
        """Verificar se há alertas baseado nas métricas"""
        alerts = []

        # Verificar error rate
        if metrics.get("error_rate", {}).get("value"):
            try:
                error_rate = float(metrics["error_rate"]["value"])
                if error_rate > 0.05:  # 5% threshold
                    alerts.append({
                        "severity": "critical" if error_rate > 0.1 else "warning",
                        "metric": "error_rate",
                        "value": error_rate,
                        "message": f"Error rate is {error_rate*100:.2f}%"
                    })
            except (ValueError, TypeError):
                pass

        # Verificar latência
        if metrics.get("request_latency_p95", {}).get("value"):
            try:
                latency = float(metrics["request_latency_p95"]["value"])
                if latency > 1.0:  # 1 second threshold
                    alerts.append({
                        "severity": "warning",
                        "metric": "latency_p95",
                        "value": latency,
                        "message": f"P95 latency is {latency:.2f}s"
                    })
            except (ValueError, TypeError):
                pass

        # Verificar CPU
        if metrics.get("cpu_usage", {}).get("value"):
            try:
                cpu = float(metrics["cpu_usage"]["value"])
                if cpu > 80:
                    alerts.append({
                        "severity": "warning",
                        "metric": "cpu_usage",
                        "value": cpu,
                        "message": f"CPU usage is {cpu:.2f}%"
                    })
            except (ValueError, TypeError):
                pass

        return alerts

    async def analyze(self) -> Dict:
        """Executar análise completa"""
        logger.info("Starting Prometheus analysis...")

        try:
            # 1. Coletar métricas
            metrics = await self.get_metrics_summary()
            logger.info(f"Collected metrics: {len(metrics)} metrics")

            # 2. Verificar alertas
            alerts = await self.check_alerts(metrics)
            logger.info(f"Found {len(alerts)} alerts")

            # 3. Analisar com LLM
            llm_analysis = await self.analyze_with_llm(metrics)
            logger.info(f"LLM analysis completed: {llm_analysis.get('status')}")

            # 4. Compilar resultado
            result = {
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "alerts": alerts,
                "analysis": llm_analysis,
                "alert_count": len(alerts),
                "critical_alerts": len([a for a in alerts if a.get("severity") == "critical"])
            }

            self.last_analysis = result
            return result

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# FastAPI App
app = FastAPI(title="Prometheus Analyzer")
analyzer = PrometheusAnalyzer(PROMETHEUS_URL, OLLAMA_URL)


@app.on_event("startup")
async def startup():
    """Inicializar analyzer"""
    await analyzer.init()
    logger.info("Prometheus Analyzer started")


@app.on_event("shutdown")
async def shutdown():
    """Fechar analyzer"""
    await analyzer.close()
    logger.info("Prometheus Analyzer stopped")


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/analyze")
async def analyze():
    """Executar análise sob demanda"""
    result = await analyzer.analyze()
    return result


@app.get("/last-analysis")
async def get_last_analysis():
    """Obter última análise"""
    if not analyzer.last_analysis:
        return {"status": "no_analysis_yet"}
    return analyzer.last_analysis


@app.get("/metrics")
async def get_metrics():
    """Obter métricas coletadas"""
    metrics = await analyzer.get_metrics_summary()
    return metrics


@app.get("/alerts")
async def get_alerts():
    """Obter alertas atuais"""
    metrics = await analyzer.get_metrics_summary()
    alerts = await analyzer.check_alerts(metrics)
    return {
        "alerts": alerts,
        "count": len(alerts),
        "critical": len([a for a in alerts if a.get("severity") == "critical"]),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyze")
async def trigger_analysis():
    """Disparar análise"""
    result = await analyzer.analyze()
    return result


# Background task para análise periódica
async def periodic_analysis():
    """Executar análise periodicamente"""
    while True:
        try:
            await asyncio.sleep(ANALYSIS_INTERVAL)
            result = await analyzer.analyze()
            logger.info(f"Periodic analysis: {result.get('alert_count', 0)} alerts")
        except Exception as e:
            logger.error(f"Periodic analysis error: {e}")


@app.on_event("startup")
async def start_background_tasks():
    """Iniciar tarefas em background"""
    # Keep a reference to the background task to avoid garbage collection
    global _bg_task
    _bg_task = asyncio.create_task(periodic_analysis())


if __name__ == "__main__":
    if _fastapi_mod is None:
        print("FastAPI is not installed; cannot run server. Install fastapi and uvicorn to run this module.")
    else:
        uvicorn.run(
            "prometheus_analyzer:app",
            host="0.0.0.0",
            port=8001,
            log_level="info",
        )
