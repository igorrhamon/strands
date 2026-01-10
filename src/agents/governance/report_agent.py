import logging
import datetime
from src.models.decision import DecisionCandidate

logger = logging.getLogger(__name__)

class ReportAgent:
    """
    Generates structured post-mortem reports for resolved incidents.
    """
    
    agent_id = "report_agent"

    def generate_post_mortem(self, candidate: DecisionCandidate) -> str:
        """
        Creates a markdown formatted post-mortem report.
        """
        logger.info(f"Generating post-mortem for {candidate.decision_id}")
        
        report = []
        report.append("# Post-Mortem Report")
        report.append(f"**Alert Reference**: {candidate.alert_reference}")
        report.append(f"**Date**: {candidate.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
        report.append(f"**Status**: {candidate.status.value}")
        report.append(f"**Resolution**: {candidate.primary_hypothesis}")
        
        report.append("\n## Executive Summary")
        report.append(candidate.summary)
        
        report.append("\n## Analysis Details")
        report.append(f"**Primary Hypothesis**: {candidate.primary_hypothesis}")
        report.append(f"**Risk Assessment**: {candidate.risk_assessment}")
        report.append(f"**Automation Level**: {candidate.automation_level.value}")
        
        if candidate.supporting_evidence:
            report.append("\n### Supporting Evidence")
            for item in candidate.supporting_evidence:
                report.append(f"- {item}")
                
        if candidate.conflicting_hypotheses:
            report.append("\n### Alternative/Conflicting Views")
            for item in candidate.conflicting_hypotheses:
                report.append(f"- {item}")
        
        if candidate.validated_at:
             report.append("\n## Governance")
             report.append(f"Validated at: {candidate.validated_at}")
             # In real usage we would have validator ID here too
        
        return "\n".join(report)
