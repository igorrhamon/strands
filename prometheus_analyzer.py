"""
Prometheus Analyzer Service
Analisa métricas do Prometheus e gera insights usando LLM (Ollama)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prometheus-analyzer")

# Configuration
PROMETHEUS_URL = "http://prometheus:9090"
OLLAMA_URL = "http://ollama:11434"
ANALYSIS_INTERVAL = 60  # Seconds
ALERT_THRESHOLD = 0.8  # 80% threshold for alerting

class PrometheusAnalyzer:
    """Analisa métricas do Prometheus e gera insights com LLM"""
    
    def __init__(self, prometheus_url: str, ollama_url: str):
        self.prometheus_url = prometheus_url
        self.ollama_url = ollama_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_analysis = {}
        
    async def init(self):
        """Inicializar sessão HTTP"""
        self.session = aiohttp.ClientSession()
        
    async def close(self):
        """Fechar sessão HTTP"""
        if self.session:
            await self.session.close()
    
    async def query_prometheus(self, query: str) -> Dict:
        """Executar query no Prometheus"""
        try:
            url = f"{self.prometheus_url}/api/v1/query"
            params = {"query": query}
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Prometheus error: {resp.status}")
                    return {"status": "error"}
        except Exception as e:
            logger.error(f"Query error: {e}")
            return {"status": "error"}
    
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
            # Preparar prompt com métricas
            prompt = self._prepare_analysis_prompt(metrics_summary)
            
            # Chamar Ollama
            url = f"{self.ollama_url}/api/generate"
            payload = {
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7,
            }
            
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return {
                        "status": "success",
                        "analysis": result.get("response", ""),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    logger.error(f"LLM error: {resp.status}")
                    return {"status": "error", "error": "LLM request failed"}
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return {"status": "error", "error": str(e)}
    
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
    asyncio.create_task(periodic_analysis())


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
