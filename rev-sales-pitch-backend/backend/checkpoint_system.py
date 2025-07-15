# checkpoint_system.py
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from agent_state import AgentCheckpoint, CheckpointType, RiskLevel, agent_manager
from risk_assessment import risk_assessor

class CheckpointManager:
    def __init__(self):
        self.pending_checkpoints: Dict[str, AgentCheckpoint] = {}
        
    def create_checkpoint(self, job_id: str, checkpoint_type: CheckpointType, 
                         data: Dict[str, Any], message: str, 
                         risk_level: RiskLevel = RiskLevel.MEDIUM) -> AgentCheckpoint:
        """Create a new checkpoint for human approval"""
        checkpoint_id = str(uuid.uuid4())
        
        checkpoint = AgentCheckpoint(
            checkpoint_id=checkpoint_id,
            type=checkpoint_type,
            data=data,
            risk_level=risk_level,
            message=message,
            requires_approval=risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM],
            created_at=datetime.now()
        )
        
        # Add to pending checkpoints
        self.pending_checkpoints[checkpoint_id] = checkpoint
        
        # Add to agent state
        agent = agent_manager.get_agent(job_id)
        if agent:
            agent.add_checkpoint(checkpoint)
            
        return checkpoint
        
    def resolve_checkpoint(self, checkpoint_id: str, decision: str, feedback: str = None) -> bool:
        """Resolve a pending checkpoint with human decision"""
        if checkpoint_id not in self.pending_checkpoints:
            return False
            
        checkpoint = self.pending_checkpoints[checkpoint_id]
        checkpoint.resolved_at = datetime.now()
        checkpoint.human_decision = decision
        checkpoint.human_feedback = feedback
        
        # Update agent state
        for agent in agent_manager.agents.values():
            agent.resolve_checkpoint(checkpoint_id, decision, feedback)
            
        # Remove from pending
        del self.pending_checkpoints[checkpoint_id]
        
        return True
        
    def get_pending_checkpoints(self, job_id: str) -> List[AgentCheckpoint]:
        """Get all pending checkpoints for a job"""
        agent = agent_manager.get_agent(job_id)
        if not agent:
            return []
            
        return [cp for cp in agent.checkpoints if cp.resolved_at is None]
        
    def create_plan_approval_checkpoint(self, job_id: str, plan_data: Dict) -> AgentCheckpoint:
        """Create checkpoint for campaign plan approval"""
        companies = plan_data.get('companies', [])
        sector = plan_data.get('sector', '')
        
        # Assess campaign risk
        risk_level, assessment = risk_assessor.assess_campaign_risk(companies, sector)
        
        message = f"Campaign plan ready for approval:\n"
        message += f"• Sector: {sector}\n"
        message += f"• Companies: {', '.join(companies)}\n"
        message += f"• Risk Level: {risk_level.value}\n"
        
        if assessment['high_risk_companies']:
            message += f"• High-risk companies: {', '.join(assessment['high_risk_companies'])}\n"
            
        message += f"• Recommendations: {'; '.join(assessment['recommendations'])}"
        
        return self.create_checkpoint(
            job_id=job_id,
            checkpoint_type=CheckpointType.PLAN_APPROVAL,
            data={'plan': plan_data, 'assessment': assessment},
            message=message,
            risk_level=risk_level
        )
        
    def create_email_preview_checkpoint(self, job_id: str, company: str, 
                                      email_content: str, context: Dict) -> AgentCheckpoint:
        """Create checkpoint for email preview and approval"""
        # Assess email content risk
        risk_level, risk_factors = risk_assessor.assess_email_content_risk(email_content, company)
        
        message = f"Email ready for {company}:\n\n"
        message += f"Subject: Opportunities for {company} with DevRev\n\n"
        message += f"Preview:\n{email_content[:200]}{'...' if len(email_content) > 200 else ''}\n\n"
        
        if risk_factors:
            message += "⚠️ Risk factors detected:\n"
            for rf in risk_factors:
                message += f"• {rf.description} - {rf.recommendation}\n"
                
        return self.create_checkpoint(
            job_id=job_id,
            checkpoint_type=CheckpointType.EMAIL_PREVIEW,
            data={
                'company': company,
                'email_content': email_content,
                'context': context,
                'risk_factors': [rf.__dict__ for rf in risk_factors]
            },
            message=message,
            risk_level=risk_level
        )
        
    def create_high_risk_company_checkpoint(self, job_id: str, company: str, 
                                          reason: str) -> AgentCheckpoint:
        """Create checkpoint for high-risk company targeting"""
        message = f"High-risk company detected: {company}\n"
        message += f"Reason: {reason}\n"
        message += "Manual approval required before proceeding."
        
        return self.create_checkpoint(
            job_id=job_id,
            checkpoint_type=CheckpointType.HIGH_RISK_COMPANY,
            data={'company': company, 'reason': reason},
            message=message,
            risk_level=RiskLevel.HIGH
        )
        
    def create_bulk_send_checkpoint(self, job_id: str, emails: Dict[str, str]) -> AgentCheckpoint:
        """Create checkpoint for bulk email sending approval"""
        email_count = len(emails)
        message = f"Ready to send {email_count} emails:\n"
        for company in emails.keys():
            message += f"• {company}\n"
        message += f"\nTotal: {email_count} emails. Proceed with sending?"
        
        return self.create_checkpoint(
            job_id=job_id,
            checkpoint_type=CheckpointType.BULK_SEND_APPROVAL,
            data={'emails': emails, 'count': email_count},
            message=message,
            risk_level=RiskLevel.MEDIUM
        )
        
    def create_error_intervention_checkpoint(self, job_id: str, error: str, 
                                           context: Dict) -> AgentCheckpoint:
        """Create checkpoint for error intervention"""
        message = f"Error encountered: {error}\n"
        message += "How should I proceed?"
        
        return self.create_checkpoint(
            job_id=job_id,
            checkpoint_type=CheckpointType.ERROR_INTERVENTION,
            data={'error': error, 'context': context},
            message=message,
            risk_level=RiskLevel.HIGH
        )

# Global checkpoint manager
checkpoint_manager = CheckpointManager()