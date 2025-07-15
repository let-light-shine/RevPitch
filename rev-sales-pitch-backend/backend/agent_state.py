# agent_state.py
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json

class AgentStatus(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERVENTION_REQUIRED = "intervention_required"

class CheckpointType(Enum):
    PLAN_APPROVAL = "plan_approval"
    EMAIL_PREVIEW = "email_preview"
    HIGH_RISK_COMPANY = "high_risk_company"
    BULK_SEND_APPROVAL = "bulk_send_approval"
    ERROR_INTERVENTION = "error_intervention"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AgentCheckpoint:
    checkpoint_id: str
    type: CheckpointType
    data: Dict[str, Any]
    risk_level: RiskLevel
    message: str
    requires_approval: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None
    human_decision: Optional[str] = None
    human_feedback: Optional[str] = None

@dataclass
class AgentPlan:
    plan_id: str
    sector: str
    target_companies: List[str]
    estimated_duration: int  # minutes
    risk_assessment: RiskLevel
    compliance_checks: Dict[str, bool]
    human_approval_required: bool
    created_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

@dataclass
class AgentAction:
    action_id: str
    type: str
    target: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    human_intervention: bool = False

class AgentState:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = AgentStatus.IDLE
        self.current_step = None
        self.plan: Optional[AgentPlan] = None
        self.checkpoints: List[AgentCheckpoint] = []
        self.actions: List[AgentAction] = []
        self.context = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def add_checkpoint(self, checkpoint: AgentCheckpoint):
        self.checkpoints.append(checkpoint)
        if checkpoint.requires_approval:
            self.status = AgentStatus.WAITING_APPROVAL
        self.updated_at = datetime.now()
        
    def resolve_checkpoint(self, checkpoint_id: str, decision: str, feedback: str = None):
        for checkpoint in self.checkpoints:
            if checkpoint.checkpoint_id == checkpoint_id:
                checkpoint.resolved_at = datetime.now()
                checkpoint.human_decision = decision
                checkpoint.human_feedback = feedback
                break
                
        # Check if all checkpoints are resolved
        pending_checkpoints = [cp for cp in self.checkpoints if cp.resolved_at is None]
        if not pending_checkpoints:
            self.status = AgentStatus.EXECUTING
            
    def add_action(self, action: AgentAction):
        self.actions.append(action)
        self.updated_at = datetime.now()
        
    def pause(self):
        self.status = AgentStatus.PAUSED
        self.updated_at = datetime.now()
        
    def resume(self):
        self.status = AgentStatus.EXECUTING
        self.updated_at = datetime.now()
        
    def complete(self):
        self.status = AgentStatus.COMPLETED
        self.updated_at = datetime.now()
        
    def fail(self, error: str):
        self.status = AgentStatus.FAILED
        self.context['error'] = error
        self.updated_at = datetime.now()
        
    def to_dict(self) -> Dict:
        return {
            'job_id': self.job_id,
            'status': self.status.value,
            'current_step': self.current_step,
            'plan': self.plan.__dict__ if self.plan else None,
            'checkpoints': [cp.__dict__ for cp in self.checkpoints],
            'actions': [action.__dict__ for action in self.actions],
            'context': self.context,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# Global agent state manager
class AgentStateManager:
    def __init__(self):
        self.agents: Dict[str, AgentState] = {}
        
    def create_agent(self, job_id: str) -> AgentState:
        agent = AgentState(job_id)
        self.agents[job_id] = agent
        return agent
        
    def get_agent(self, job_id: str) -> Optional[AgentState]:
        return self.agents.get(job_id)
        
    def remove_agent(self, job_id: str):
        if job_id in self.agents:
            del self.agents[job_id]
            
    def list_active_agents(self) -> List[AgentState]:
        return [agent for agent in self.agents.values() 
                if agent.status not in [AgentStatus.COMPLETED, AgentStatus.FAILED]]

# Global instance
agent_manager = AgentStateManager()