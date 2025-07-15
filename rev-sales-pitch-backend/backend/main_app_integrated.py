# main_app_integrated.py
import os
import uuid
import asyncio
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional
from datetime import datetime
# Import our new agent system
from agent_state import agent_manager, AgentStatus
from checkpoint_system import checkpoint_manager
from safety_controls import safety_controller, ComplianceStatus
from agent_campaign_updated import run_agent_campaign
from risk_assessment import risk_assessor

# Your existing imports
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="RevReach Agent - Professional Sales AI")

# Request Models
class AgentCampaignRequest(BaseModel):
    sector: str
    recipient_email: EmailStr
    autonomy_level: str = "guided"  # supervised, guided, autonomous
    
class CheckpointDecision(BaseModel):
    checkpoint_id: str
    decision: str  # approve, reject, modify
    feedback: Optional[str] = None
    modified_content: Optional[str] = None

class AgentIntervention(BaseModel):
    job_id: str
    action: str  # pause, resume, stop, emergency_stop

# Main Campaign Endpoint
@app.post("/start-agent-campaign")
async def start_agent_campaign(request: AgentCampaignRequest):
    """Start AI agent campaign with proper checkpoints and safety controls"""
    
    # Pre-flight safety checks
    campaign_check = safety_controller.check_campaign_limits()
    if campaign_check.status == ComplianceStatus.VIOLATION:
        raise HTTPException(
            status_code=429, 
            detail=f"Campaign limit exceeded: {campaign_check.message}"
        )
    
    # Create job ID and initialize agent
    job_id = str(uuid.uuid4())
    agent = agent_manager.create_agent(job_id)
    
    # Record campaign start
    safety_controller.record_campaign_started()
    
    # Start agent campaign in background
    asyncio.create_task(run_agent_campaign(
        sector=request.sector,
        job_id=job_id,
        recipient_email=request.recipient_email
    ))
    
    return {
        "message": f"🤖 Agent campaign started for {request.sector}",
        "job_id": job_id,
        "agent_status": agent.status.value,
        "autonomy_level": request.autonomy_level,
        "safety_check": campaign_check.message
    }

# Agent Status & Monitoring
@app.get("/agent-status/{job_id}")
async def get_agent_status(job_id: str):
    """Get comprehensive agent status"""
    agent = agent_manager.get_agent(job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get pending checkpoints
    pending_checkpoints = checkpoint_manager.get_pending_checkpoints(job_id)
    
    # Calculate progress
    progress = calculate_agent_progress(agent)
    
    return {
        "job_id": job_id,
        "agent_status": agent.status.value,
        "current_step": agent.current_step,
        "progress": progress,
        "agent_message": get_agent_message(agent),
        "pending_checkpoints": [
            {
                "checkpoint_id": cp.checkpoint_id,
                "type": cp.type.value,
                "message": cp.message,
                "risk_level": cp.risk_level.value,
                "requires_approval": cp.requires_approval,
                "created_at": cp.created_at.isoformat(),
                "data": cp.data
            }
            for cp in pending_checkpoints
        ],
        "recent_actions": [
            {
                "action_id": action.action_id,
                "type": action.type,
                "target": action.target,
                "status": action.status,
                "started_at": action.started_at.isoformat(),
                "completed_at": action.completed_at.isoformat() if action.completed_at else None,
                "duration": get_action_duration(action),
                "error": action.error
            }
            for action in agent.actions[-10:]  # Last 10 actions
        ],
        "stats": {
            "total_checkpoints": len(agent.checkpoints),
            "resolved_checkpoints": len([cp for cp in agent.checkpoints if cp.resolved_at]),
            "total_actions": len(agent.actions),
            "successful_actions": len([a for a in agent.actions if a.status == "completed"]),
            "failed_actions": len([a for a in agent.actions if a.status == "failed"])
        }
    }

# Checkpoint Management
@app.post("/approve-checkpoint")
async def approve_checkpoint(decision: CheckpointDecision):
    """Approve, reject, or modify an agent checkpoint"""
    
    # Validate checkpoint exists
    if decision.checkpoint_id not in checkpoint_manager.pending_checkpoints:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    checkpoint = checkpoint_manager.pending_checkpoints[decision.checkpoint_id]
    
    # Additional safety check for high-risk decisions
    if checkpoint.risk_level.value == "high" and decision.decision == "approve":
        if not decision.feedback:
            raise HTTPException(
                status_code=400, 
                detail="High-risk approvals require feedback/justification"
            )
    
    # Handle different decision types
    if decision.decision == "approve":
        success = checkpoint_manager.resolve_checkpoint(
            decision.checkpoint_id, "approve", decision.feedback
        )
        message = "✅ Checkpoint approved - Agent continuing"
        
    elif decision.decision == "reject":
        success = checkpoint_manager.resolve_checkpoint(
            decision.checkpoint_id, "reject", decision.feedback
        )
        message = "❌ Checkpoint rejected - Agent stopping"
        
    elif decision.decision == "modify":
        if not decision.modified_content:
            raise HTTPException(
                status_code=400, 
                detail="Modified content required for modify decision"
            )
        
        # Store modified content in checkpoint data
        checkpoint.data["modified_content"] = decision.modified_content
        success = checkpoint_manager.resolve_checkpoint(
            decision.checkpoint_id, "modify", decision.feedback
        )
        message = "✏️ Checkpoint modified - Agent using updated content"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid decision type")
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resolve checkpoint")
    
    return {
        "message": message,
        "checkpoint_id": decision.checkpoint_id,
        "decision": decision.decision,
        "timestamp": datetime.now().isoformat()
    }

# Agent Intervention
@app.post("/agent-intervention")
async def agent_intervention(intervention: AgentIntervention):
    """Intervene in agent execution (pause, resume, stop)"""
    agent = agent_manager.get_agent(intervention.job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if intervention.action == "pause":
        if agent.status == AgentStatus.EXECUTING:
            agent.pause()
            return {
                "message": "⏸️ Agent paused",
                "new_status": agent.status.value,
                "can_resume": True
            }
        else:
            raise HTTPException(400, detail="Can only pause executing agents")
    
    elif intervention.action == "resume":
        if agent.status == AgentStatus.PAUSED:
            agent.resume()
            return {
                "message": "▶️ Agent resumed",
                "new_status": agent.status.value
            }
        else:
            raise HTTPException(400, detail="Agent is not paused")
    
    elif intervention.action == "stop":
        agent.complete()
        safety_controller.record_campaign_completed()
        return {
            "message": "⏹️ Agent stopped gracefully",
            "new_status": agent.status.value
        }
    
    elif intervention.action == "emergency_stop":
        agent.fail("Emergency stop requested by human")
        safety_controller.record_campaign_completed()
        return {
            "message": "🚨 Agent emergency stopped",
            "new_status": agent.status.value
        }
    
    else:
        raise HTTPException(400, detail="Invalid intervention action")

# Dashboard Views
@app.get("/agent-dashboard")
async def get_agent_dashboard():
    """Get overview dashboard for all agents"""
    active_agents = agent_manager.list_active_agents()
    all_pending = []
    
    # Collect all pending checkpoints
    for agent in active_agents:
        pending = checkpoint_manager.get_pending_checkpoints(agent.job_id)
        for checkpoint in pending:
            all_pending.append({
                "job_id": agent.job_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "type": checkpoint.type.value,
                "message": checkpoint.message,
                "risk_level": checkpoint.risk_level.value,
                "created_at": checkpoint.created_at.isoformat()
            })
    
    # Get safety status
    safety_status = safety_controller._get_current_limits()
    
    return {
        "summary": {
            "active_agents": len(active_agents),
            "pending_checkpoints": len(all_pending),
            "total_campaigns_today": safety_status["daily_campaigns"]["current"],
            "emails_sent_today": safety_status["daily_emails"]["current"]
        },
        "active_agents": [
            {
                "job_id": agent.job_id,
                "status": agent.status.value,
                "current_step": agent.current_step,
                "progress": calculate_agent_progress(agent),
                "pending_checkpoints": len(checkpoint_manager.get_pending_checkpoints(agent.job_id)),
                "created_at": agent.created_at.isoformat()
            }
            for agent in active_agents
        ],
        "pending_checkpoints": all_pending,
        "safety_status": safety_status
    }

# Agent Analytics
@app.get("/agent-analytics/{job_id}")
async def get_agent_analytics(job_id: str):
    """Get detailed performance analytics for an agent"""
    agent = agent_manager.get_agent(job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Calculate performance metrics
    total_actions = len(agent.actions)
    successful_actions = len([a for a in agent.actions if a.status == "completed"])
    failed_actions = len([a for a in agent.actions if a.status == "failed"])
    
    # Calculate time analytics
    action_times = {}
    total_duration = 0
    
    for action in agent.actions:
        if action.completed_at and action.started_at:
            duration = (action.completed_at - action.started_at).total_seconds()
            total_duration += duration
            
            if action.type not in action_times:
                action_times[action.type] = []
            action_times[action.type].append(duration)
    
    # Average times per action type
    avg_action_times = {
        action_type: {
            "avg_seconds": sum(times) / len(times),
            "count": len(times),
            "total_seconds": sum(times)
        }
        for action_type, times in action_times.items()
    }
    
    # Checkpoint analytics
    resolved_checkpoints = [cp for cp in agent.checkpoints if cp.resolved_at]
    checkpoint_resolution_times = []
    
    for cp in resolved_checkpoints:
        if cp.resolved_at:
            resolution_time = (cp.resolved_at - cp.created_at).total_seconds()
            checkpoint_resolution_times.append(resolution_time)
    
    checkpoint_stats = {
        "total_checkpoints": len(agent.checkpoints),
        "resolved_checkpoints": len(resolved_checkpoints),
        "pending_checkpoints": len(agent.checkpoints) - len(resolved_checkpoints),
        "avg_resolution_time": sum(checkpoint_resolution_times) / len(checkpoint_resolution_times) if checkpoint_resolution_times else 0,
        "approval_rate": len([cp for cp in resolved_checkpoints if cp.human_decision == "approve"]) / max(len(resolved_checkpoints), 1) * 100,
        "modification_rate": len([cp for cp in resolved_checkpoints if cp.human_decision == "modify"]) / max(len(resolved_checkpoints), 1) * 100
    }
    
    return {
        "job_id": job_id,
        "agent_status": agent.status.value,
        "performance": {
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "failed_actions": failed_actions,
            "success_rate": (successful_actions / max(total_actions, 1)) * 100,
            "total_duration_minutes": total_duration / 60,
            "avg_action_times": avg_action_times
        },
        "checkpoint_analytics": checkpoint_stats,
        "timeline": [
            {
                "timestamp": action.started_at.isoformat(),
                "type": action.type,
                "target": action.target,
                "status": action.status,
                "duration_seconds": get_action_duration(action)
            }
            for action in agent.actions
        ]
    }

# Safety & Compliance
@app.get("/safety-status")
async def get_safety_status():
    """Get current safety and compliance status"""
    limits = safety_controller._get_current_limits()
    
    return {
        "current_limits": limits,
        "compliance_status": "healthy",  # Could be enhanced with more checks
        "alerts": [],  # Any active safety alerts
        "recommendations": [
            "All systems operating within normal parameters",
            f"Daily email limit: {limits['daily_emails']['remaining']} remaining",
            f"Daily campaigns: {limits['daily_campaigns']['remaining']} remaining"
        ]
    }

@app.post("/emergency-stop-all")
async def emergency_stop_all(reason: str = "Manual emergency stop"):
    """Emergency stop all active agents"""
    active_agents = agent_manager.list_active_agents()
    stopped_count = 0
    
    for agent in active_agents:
        agent.fail(f"Emergency stop: {reason}")
        stopped_count += 1
    
    safety_controller.emergency_stop_all_campaigns(reason)
    
    return {
        "message": f"🚨 Emergency stop executed",
        "agents_stopped": stopped_count,
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    }

# Utility functions
def calculate_agent_progress(agent) -> int:
    """Calculate agent progress percentage"""
    if agent.status == AgentStatus.COMPLETED:
        return 100
    elif agent.status == AgentStatus.FAILED:
        return 0
    elif agent.status == AgentStatus.WAITING_APPROVAL:
        return max(50, get_step_progress(agent.current_step))  # At least 50% if waiting
    
    return get_step_progress(agent.current_step)

def get_step_progress(step: str) -> int:
    """Map step to progress percentage"""
    progress_map = {
        "initializing": 5,
        "planning": 15,
        "gathering_context": 35,
        "generating_emails": 60,
        "requesting_send_approval": 80,
        "sending_emails": 95,
        "completed": 100
    }
    return progress_map.get(step, 0)

def get_agent_message(agent) -> str:
    """Get human-readable agent status message"""
    if agent.status == AgentStatus.PLANNING:
        return "🧠 Analyzing sector and planning campaign strategy..."
    elif agent.status == AgentStatus.WAITING_APPROVAL:
        pending = len([cp for cp in agent.checkpoints if not cp.resolved_at])
        return f"⏳ Waiting for human approval ({pending} pending decisions)"
    elif agent.status == AgentStatus.EXECUTING:
        return f"🚀 {agent.current_step.replace('_', ' ').title()}..."
    elif agent.status == AgentStatus.PAUSED:
        return "⏸️ Agent paused - can be resumed"
    elif agent.status == AgentStatus.COMPLETED:
        return "✅ Campaign completed successfully"
    elif agent.status == AgentStatus.FAILED:
        return f"❌ Agent failed: {agent.context.get('error', 'Unknown error')}"
    elif agent.status == AgentStatus.INTERVENTION_REQUIRED:
        return "🚨 Human intervention required"
    else:
        return "🤖 Agent active"

def get_action_duration(action) -> Optional[float]:
    """Get action duration in seconds"""
    if action.completed_at and action.started_at:
        return (action.completed_at - action.started_at).total_seconds()
    return None

# Health Check
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    active_agents = len(agent_manager.list_active_agents())
    pending_checkpoints = len(checkpoint_manager.pending_checkpoints)
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agents": {
            "active": active_agents,
            "total_created": len(agent_manager.agents)
        },
        "checkpoints": {
            "pending": pending_checkpoints
        },
        "safety": "all systems normal"
    }

@app.get("/")
async def root():
    """API root with welcome message"""
    return {
        "message": "🤖 RevReach Agent API",
        "description": "Professional AI Sales Campaign Manager with Human Oversight",
        "version": "2.0.0",
        "features": [
            "AI-powered sales intelligence",
            "Human checkpoint system",
            "Safety controls & compliance",
            "Real-time monitoring",
            "Risk assessment",
            "Campaign analytics"
        ],
        "endpoints": {
            "start_campaign": "/start-agent-campaign",
            "agent_status": "/agent-status/{job_id}",
            "dashboard": "/agent-dashboard",
            "safety": "/safety-status"
        }
    }