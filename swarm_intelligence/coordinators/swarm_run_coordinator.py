import asyncio
import random
import logging
import time
import uuid
import logging
import uuid
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from datetime import datetime, timezone

from swarm_intelligence.core.models import (
    SwarmPlan,
    Alert,
    Decision,
    AgentExecution,
    RetryAttempt,
    RetryDecision,
    HumanDecision,
    SwarmStep,
    Domain,
    SwarmRun
)
from swarm_intelligence.core.monitor_policy import MonitorPolicy, MonitorState, EscalationAction
from swarm_intelligence.controllers.swarm_execution_controller import (
    SwarmExecutionController,
)
from swarm_intelligence.controllers.swarm_retry_controller import SwarmRetryController
from swarm_intelligence.controllers.swarm_decision_controller import (
    SwarmDecisionController,
)
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.policy.confidence_policy import (
    ConfidencePolicy,
    DefaultConfidencePolicy,
)
from src.deduplication.distributed_deduplicator import DistributedEventDeduplicator, DeduplicationAction

logger = logging.getLogger(__name__)

class SwarmRunCoordinator:
    """
    Orchestrates the specialized controllers to run a swarm plan.
    This component is stateful for a single run.
    """

    def __init__(
        self,
        execution_controller: SwarmExecutionController,
        retry_controller: SwarmRetryController,
        decision_controller: SwarmDecisionController,
        confidence_service: ConfidenceService,
        llm_agent_id: Optional[str] = "llm_agent",
        deduplicator: Optional[DistributedEventDeduplicator] = None,
    ):
        self.execution_controller = execution_controller
        self.retry_controller = retry_controller
        self.decision_controller = decision_controller
        self.confidence_service = confidence_service
        self.llm_agent_id = llm_agent_id
        self.deduplicator = deduplicator or DistributedEventDeduplicator()
        
        # Scheduler para decisões MONITOR
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self.monitor_states: Dict[str, MonitorState] = {}
        
        # Cache em memória para o Console Operacional (em produção usar Redis/DB)
        self._execution_history: Dict[str, Dict[str, Any]] = {}

    async def aexecute_plan(
        self,
        domain: Domain,
        plan: SwarmPlan,
        alert: Alert,
        run_id: str,
        confidence_policy: Optional[ConfidencePolicy] = None,
        human_hook: Optional[Callable[[Decision], HumanDecision]] = None,
        replay_mode: bool = False,
        replay_results: Optional[Dict[str, AgentExecution]] = None,
        master_seed: Optional[int] = None,
        max_retry_rounds: int = 10,
        max_runtime_seconds: float = 300000.0,
        max_total_attempts: int = 50,
        use_llm_fallback: bool = True,
        llm_fallback_threshold: float = 0.5,
    ) -> tuple[SwarmRun, List[RetryAttempt], List[RetryDecision]]:
        
        # Registrar início da execução para o console
        self._execution_history[run_id] = {
            "run_id": run_id,
            "status": "RUNNING",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "alert_name": alert.data.get("alertname", "Unknown Alert"),
            "domain": domain.name if hasattr(domain, 'name') else str(domain),
            "risk_level": alert.data.get("severity", "MEDIUM").upper(),
            "agents": [],
            "confidence_breakdown": {},
            "rag_evidence": [],
            "retries": [],
            "raw_data": alert.data
        }

        start_time = time.time()
        # 0. Distributed Deduplication Check
        if not replay_mode and self.deduplicator:
            # Generate alert signature for dedup
            source_id = alert.alert_id
            severity = alert.data.get("severity", "warning")
            service = alert.data.get("service", "unknown")
            
            # Try to acquire a distributed lock to prevent race conditions
            lock_name = f"swarm_run:{source_id}"
            if self.deduplicator.acquire_lock(lock_name):
                try:
                    action, existing_run_id = self.deduplicator.check_duplicate(
                        source_id=source_id,
                        event_data=alert.data,
                        severity=severity,
                        source_system=alert.data.get("source", "grafana")
                    )
                    
                    if action == DeduplicationAction.UPDATE_EXISTING:
                        # In a real scenario, we might want to attach this alert to the existing run
                        self.metrics.record_dedup("update_existing")
                        pass 
                finally:
                    self.deduplicator.release_lock(lock_name)

        # Use a local RNG to avoid modifying global random state
        if master_seed is None:
            master_seed = random.randint(0, 1_000_000)

        local_rng = random.Random(master_seed)

        all_retry_attempts = []
        all_retry_decisions = []
        all_executions: List[AgentExecution] = []
        # Start with an empty set; computing here would always be empty because
        # `all_executions` is still empty at this point. It is recomputed later
        # after executions are appended.
        successful_step_ids = set()
        
        

        round_counter = 0
        total_attempts_counter = 0
        aborted_by_limit = False

        steps_to_process = list(plan.steps)

        for step in steps_to_process:
            self.confidence_service.apply_time_decay(step.agent_id, 0.001)

        async def _internal_run():
            nonlocal steps_to_process, round_counter, total_attempts_counter, aborted_by_limit

            while steps_to_process:
                if round_counter >= max_retry_rounds or total_attempts_counter >= max_total_attempts:
                    aborted_by_limit = True
                    break

                round_counter += 1
                total_attempts_counter += len(steps_to_process)

                new_executions = await self.execution_controller.execute(
                    steps_to_process, replay_mode, replay_results
                )
                
                # Registrar execuções para o console
                for ex in new_executions:
                    self._record_agent_step(run_id, ex)
                
                all_executions.extend(new_executions)
                # evaluate(self, run_id: str, step_id: str, error: Exception) -> RetryDecision:
                retry_decision = self.retry_controller.evaluate(
                    run_id, steps_to_process[0].step_id if steps_to_process else "", Exception("Simulated error for retry evaluation")
                )
                
                reply_decision = self.retry_controller.evaluate(run_id, "", Exception("Simulated error for retry evaluation"))
                all_retry_decisions.append(retry_decision)
                

        try:
            #await asyncio.wait_for(_internal_run(), timeout=max_runtime_seconds)
            await asyncio.wait_for(_internal_run(), timeout=300000.0)
        except asyncio.TimeoutError:
            aborted_by_limit = True

        successful_step_ids = {ex.step_id for ex in all_executions if ex.is_successful() and ex.step_id}
        final_successful_executions = [
            ex for ex in all_executions if ex.step_id in successful_step_ids
        ]

        swarm_run = SwarmRun(
            run_id=run_id,
            domain=domain,
            plan=plan,
            master_seed=master_seed,
            executions=all_executions,
        )
        swarm_run.metadata = {
            "total_rounds": round_counter,
            "total_attempts": total_attempts_counter,
            "aborted_by_limit": aborted_by_limit,
        }

        all_mandatory_successful = all(
            s.step_id in successful_step_ids for s in plan.steps if s.mandatory
        )

        current_avg_confidence = 0.0
        if final_successful_executions:
            all_evidence = [ev for ex in final_successful_executions for ev in ex.output_evidence]
            if all_evidence:
                current_avg_confidence = sum(ev.confidence for ev in all_evidence) / len(all_evidence)

        should_trigger_llm = (
            use_llm_fallback
            and self.llm_agent_id is not None
            and (
                (not all_mandatory_successful)
                or (current_avg_confidence <= llm_fallback_threshold)
            )
        )
        
        should_trigger_llm = True
        
        if should_trigger_llm:
            llm_input = {
                "alert": alert.data,
                "run_id": run_id,
                "evidence": [
                    {
                        "agent_id": ev.agent_id,
                        "confidence": ev.confidence,
                        "content": ev.content,
                    }
                    for ex in final_successful_executions
                    for ev in ex.output_evidence
                ],
                "avg_confidence": current_avg_confidence,
                "mandatory_success": all_mandatory_successful,
            }
            llm_agent = self.llm_agent_id or "llm_agent"
            llm_step = SwarmStep(agent_id=llm_agent, mandatory=True, parameters=llm_input)
            llm_executions = await self.execution_controller.execute([llm_step])
            for ex in llm_executions:
                self._record_agent_step(run_id, ex)
            all_executions.extend(llm_executions)
            final_successful_executions.extend([ex for ex in llm_executions if ex and ex.is_successful()])

        decision = await self.decision_controller.decide(
            plan,
            final_successful_executions,
            alert,
            self.confidence_service,
            confidence_policy or DefaultConfidencePolicy(),
            human_hook,
            run_id,
            master_seed,
        )

        swarm_run.executions = all_executions
        swarm_run.final_decision = decision

        # --- Lógica de MONITOR Proativo ---
        if decision.action_proposed.upper() == "MONITOR" and not replay_mode:
            await self._handle_monitor_decision(domain, plan, alert, run_id, decision)

        # Registrar decisão final para o console
        if run_id in self._execution_history:
            self._execution_history[run_id]["status"] = "FINISHED"
            self._execution_history[run_id]["final_decision"] = decision.action_proposed
            self._execution_history[run_id]["final_confidence"] = decision.confidence
            self._execution_history[run_id]["confidence_breakdown"] = {
                "base_score": decision.confidence,
                "explanation": decision.summary,
                "factors": decision.metadata or {}
            }

        # Register successful execution in deduplicator
        if not replay_mode and self.deduplicator:
            self.deduplicator.register_execution(
                source_id=alert.alert_id,
                execution_id=run_id,
                event_data=alert.data,
                severity=alert.data.get("severity"),
                source_system=alert.data.get("source")
            )

        return swarm_run, all_retry_attempts, all_retry_decisions

    def _record_agent_step(self, run_id: str, execution: AgentExecution):
        """Registra um passo de agente no histórico para o console."""
        if run_id in self._execution_history:
            status = "SUCCESS" if execution.is_successful() else "FAILED"
            # Safely format latency if available and numeric
            latency_val = getattr(execution, 'duration_seconds', None)
            latency_str = f"{latency_val:.2f}s" if isinstance(latency_val, (int, float)) else "0.0s"
            step = {
                "name": execution.agent_id,
                "status": status,
                "latency": latency_str,
                #"latency": f"{execution.duration_seconds:.2f}s" if hasattr(execution, 'duration_seconds') else "0.0s",
                "details": f"Agent {execution.agent_id} finished with status {status}"
            }
            self._execution_history[run_id]["agents"].append(step)

    # --- API Endpoints para o Console Operacional ---

    def get_run_details(self, run_id: str) -> Optional[Dict]:
        """Retorna detalhes de uma execução específica."""
        return self._execution_history.get(run_id)

    def get_run_agents(self, run_id: str) -> List[Dict]:
        """Retorna a timeline de agentes de uma execução."""
        run = self._execution_history.get(run_id)
        return run.get("agents", []) if run else []

    def get_run_confidence(self, run_id: str) -> Dict:
        """Retorna o breakdown de confiança de uma execução."""
        run = self._execution_history.get(run_id)
        return run.get("confidence_breakdown", {}) if run else {}

    def get_run_rag_evidence(self, run_id: str) -> List[Dict]:
        """Retorna as evidências de RAG de uma execução."""
        run = self._execution_history.get(run_id)
        return run.get("rag_evidence", []) if run else []

    def get_run_retries(self, run_id: str) -> List[Dict]:
        """Retorna o histórico de retries de uma execução."""
        run = self._execution_history.get(run_id)
        return run.get("retries", []) if run else []

    def get_all_runs(self) -> List[Dict]:
        """Retorna lista de todas as execuções recentes."""
        return list(self._execution_history.values())

    async def _handle_monitor_decision(self, domain: Domain, plan: SwarmPlan, alert: Alert, run_id: str, decision: Decision):
        """Agenda a reexecução para decisões MONITOR."""
        policy = decision.monitor_policy or MonitorPolicy()
        
        state = self.monitor_states.get(run_id)
        if not state:
            state = MonitorState(run_id=run_id, original_alert_id=alert.alert_id)
            self.monitor_states[run_id] = state

        if state.recheck_count < policy.max_rechecks:
            state.recheck_count += 1
            state.last_recheck_timestamp = datetime.now(timezone.utc).timestamp()
            
            delay = policy.recheck_after_minutes
            next_run_time = datetime.now(timezone.utc) + timedelta(minutes=delay)
            
            logger.info(f"Decision is MONITOR. Scheduling re-check #{state.recheck_count} for run {run_id} in {delay} minutes.")
            
            self.scheduler.add_job(
                self.aexecute_plan,
                'date',
                run_date=next_run_time,
                args=[domain, plan, alert, f"{run_id}_recheck_{state.recheck_count}"],
                kwargs={"master_seed": random.randint(0, 1000000)}
            )
        else:
            logger.warning(f"Max re-checks reached for run {run_id}. Triggering escalation: {policy.escalation_action}")
            await self._trigger_escalation(run_id, policy.escalation_action)

    async def _trigger_escalation(self, run_id: str, action: EscalationAction):
        """Executa a ação de escalonamento quando o limite de MONITOR é atingido."""
        if run_id in self._execution_history:
            self._execution_history[run_id]["status"] = "ESCALATED"
            self._execution_history[run_id]["metadata"]["escalation_action"] = action
        
        # Aqui poderíamos disparar um alerta real, abrir um ticket ou forçar uma ação humana
        logger.error(f"ESCALATION TRIGGERED for {run_id}: {action}")

