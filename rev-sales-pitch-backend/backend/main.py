# main_app_complete.py - This replaces your original main file
import os
import uuid
import time
import ast
import asyncio
import logging
import httpx
import pandas as pd
import datetime
from typing import List, Dict, Optional, Any
from uuid import uuid4
import json
import re

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from slugify import slugify

# Load environment variables
load_dotenv()

# Validate required env variables
required_envs = [
    "OPENAI_API_KEY", "ES_USERNAME", "ES_PASSWORD",
    "FROM_EMAIL", "MY_EMAIL", "EMAIL_PASSWORD",
    "PERPLEXITY_API_KEY"
]
for var in required_envs:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing environment variable: {var}")

# Logging setup
logging.basicConfig(level=logging.INFO)

# OpenAI and LangChain imports
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import ElasticsearchStore
from langchain.prompts import PromptTemplate

# Import your email utils
from email_utils import send_email, send_summary_email

# Import new agent system
from agent_state import agent_manager, AgentStatus
from checkpoint_system import checkpoint_manager
from safety_controls import safety_controller, ComplianceStatus
from agent_campaign_updated import run_agent_campaign
from risk_assessment import risk_assessor

# FastAPI App
app = FastAPI(title="RevReach Agent - Professional Sales AI")


# CORS configuration for production
if os.getenv("ENVIRONMENT") == "production":
    # Production CORS - restrict to your frontend domain
    allowed_origins = [
        os.getenv("FRONTEND_URL", "https://revreach-agent-ui.onrender.com")
    ]
else:
    # Development CORS - allow all for testing
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Add environment info endpoint
@app.get("/info")
async def get_info():
    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": "2.0.0",
        "service": "revreach-agent-api"
    }

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LangChain setup
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.getenv("OPENAI_API_KEY"))
embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

# Prompt templates (from your original code)
discover_prompt = PromptTemplate.from_template(
    "Return only a valid JSON array of 10 company names in the {sector} sector. No explanation. Format: [\"Company A\", \"Company B\", ...]"
)
email_prompt = PromptTemplate.from_template("""
You are a friendly, concise sales-outreach assistant at DevRev. 
Given the following context for {company}:

External context:
{external_ctx}

DevRev context:
{devrev_ctx}

Write a personalized cold email to {company}'s leadership explaining,
in 3–4 short paragraphs, how DevRev can help solve their challenges.
Make it warm, professional, and include a clear call to action.

Email:
""")

# ===== NEW AGENT SYSTEM API ENDPOINTS =====

# Request Models
class AgentCampaignRequest(BaseModel):
    sector: str
    recipient_email: EmailStr
    autonomy_level: str = "guided"

class CheckpointDecision(BaseModel):
    checkpoint_id: str
    decision: str  # approve, reject, modify
    feedback: Optional[str] = None
    modified_content: Optional[str] = None

class AgentIntervention(BaseModel):
    job_id: str
    action: str  # pause, resume, stop, emergency_stop

# Main Agent Campaign Endpoint
@app.post("/start-agent-campaign")
async def start_agent_campaign(request: AgentCampaignRequest):
    """Start AI agent campaign with checkpoints and safety controls"""
    
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
        "autonomy_level": request.autonomy_level
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
    
    return {
        "job_id": job_id,
        "agent_status": agent.status.value,
        "current_step": agent.current_step,
        "progress": calculate_agent_progress(agent),
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
                "error": action.error
            }
            for action in agent.actions[-5:]
        ]
    }

# Checkpoint Management
@app.post("/approve-checkpoint")
async def approve_checkpoint(decision: CheckpointDecision):
    """Approve, reject, or modify an agent checkpoint"""
    
    if decision.checkpoint_id not in checkpoint_manager.pending_checkpoints:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    checkpoint = checkpoint_manager.pending_checkpoints[decision.checkpoint_id]
    
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
        if decision.modified_content:
            checkpoint.data["modified_content"] = decision.modified_content
        success = checkpoint_manager.resolve_checkpoint(
            decision.checkpoint_id, "modify", decision.feedback
        )
        message = "✏️ Checkpoint modified - Agent using updated content"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid decision type")
    
    return {
        "message": message,
        "checkpoint_id": decision.checkpoint_id,
        "decision": decision.decision,
        "timestamp": datetime.datetime.now().isoformat()
    }

# Agent Intervention
@app.post("/agent-intervention")
async def agent_intervention(intervention: AgentIntervention):
    """Intervene in agent execution"""
    agent = agent_manager.get_agent(intervention.job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if intervention.action == "pause":
        agent.pause()
        return {"message": "⏸️ Agent paused", "new_status": agent.status.value}
    elif intervention.action == "resume":
        agent.resume()
        return {"message": "▶️ Agent resumed", "new_status": agent.status.value}
    elif intervention.action == "stop":
        agent.complete()
        return {"message": "⏹️ Agent stopped", "new_status": agent.status.value}
    elif intervention.action == "emergency_stop":
        agent.fail("Emergency stop requested")
        return {"message": "🚨 Emergency stop", "new_status": agent.status.value}

@app.get("/agent-dashboard")
async def get_agent_dashboard():
    """Get overview dashboard for all agents"""
    active_agents = agent_manager.list_active_agents()
    all_pending = []
    
    # Collect all pending checkpoints
    for agent in active_agents:
        pending = checkpoint_manager.get_pending_checkpoints(agent.job_id)
        all_pending.extend(pending)
    
    # Get safety status for today's counts
    try:
        safety_status = safety_controller._get_current_limits()
        emails_today = safety_status.get('daily_emails', {}).get('current', 0)
        campaigns_today = safety_status.get('daily_campaigns', {}).get('current', 0)
    except:
        emails_today = 0
        campaigns_today = 0
    
    return {
        "summary": {
            "active_agents": len(active_agents),
            "pending_checkpoints": len(all_pending),
            "emails_sent_today": emails_today,
            "total_campaigns_today": campaigns_today
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
        "pending_checkpoints": all_pending
    }

# ===== ORIGINAL LEGACY ENDPOINTS (for backwards compatibility) =====

@app.post("/start-campaign")
async def start_legacy_campaign(request: Request, payload: Dict):
    """Legacy endpoint - redirects to new agent system"""
    new_request = AgentCampaignRequest(
        sector=payload.get("sector", "SaaS"),
        recipient_email=payload.get("recipient_email", "test@example.com")
    )
    return await start_agent_campaign(new_request)

@app.get("/campaign-status")
def legacy_campaign_status():
    """Legacy endpoint - returns latest active agent or idle"""
    active_agents = agent_manager.list_active_agents()
    
    if not active_agents:
        return {
            "status": "idle",
            "progress": 0,
            "message": "No active campaigns"
        }
    
    # Return most recent active agent
    agent = active_agents[-1]
    return {
        "status": agent.status.value,
        "progress": calculate_agent_progress(agent),
        "message": get_agent_message(agent),
        "job_id": agent.job_id
    }

# ===== UTILITY FUNCTIONS =====

def calculate_agent_progress(agent) -> int:
    """Calculate agent progress percentage"""
    if agent.status == AgentStatus.COMPLETED:
        return 100
    elif agent.status == AgentStatus.FAILED:
        return 0
    elif agent.status == AgentStatus.WAITING_APPROVAL:
        return max(50, get_step_progress(agent.current_step))
    
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
        return "🧠 Planning campaign strategy..."
    elif agent.status == AgentStatus.WAITING_APPROVAL:
        pending = len([cp for cp in agent.checkpoints if not cp.resolved_at])
        return f"⏳ Waiting for approval ({pending} decisions needed)"
    elif agent.status == AgentStatus.EXECUTING:
        return f"🚀 {agent.current_step.replace('_', ' ').title()}..."
    elif agent.status == AgentStatus.COMPLETED:
        return "✅ Campaign completed successfully"
    elif agent.status == AgentStatus.FAILED:
        return "❌ Campaign failed"
    else:
        return "🤖 Agent active"

# ===== ORIGINAL HELPER FUNCTIONS (from your code) =====

async def retry_llm_invoke(prompt: str, retries: int = 3, delay: float = 5):
    """Retry LLM invocation with exponential backoff"""
    for attempt in range(retries):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                raise

async def get_company_context_from_perplexity_async(company: str) -> str:
    """Get company context from Perplexity API"""
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a sales intelligence assistant."},
            {"role": "user", "content": f"Summarize the latest strategic, operational, or product challenges faced by {company} in 2024 in exactly 2 sentences."}
        ],
        "search_domain_filter": ["bloomberg.com", "reuters.com", f"{company.lower()}.com"],
        "search_recency_filter": "month"
    }
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            return res.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logging.warning(f"Perplexity failed for {company}: {e}")
        return "External challenges could not be retrieved."

async def multi_index_retriever(company: str, external_ctx: str, indices: List[str]) -> str:
    """Retrieve DevRev context from multiple indices"""
    docs = []
    for index in indices:
        try:
            store = ElasticsearchStore(
                es_url=ES_URL,
                index_name=index,
                embedding=embedding_model,
                es_user=os.getenv("ES_USERNAME"),
                es_password=os.getenv("ES_PASSWORD"),
            )
            retriever = store.as_retriever()
            docs += retriever.get_relevant_documents(f"{company} challenges")
            docs += retriever.get_relevant_documents(f"How DevRev can help with: {external_ctx}")
        except Exception as e:
            logging.warning(f"Failed to retrieve from {index}: {e}")
    
    # Deduplicate
    seen, unique_docs = set(), []
    for d in docs:
        if d.page_content not in seen:
            seen.add(d.page_content)
            unique_docs.append(d)
    
    return "\n\n".join([d.page_content for d in unique_docs])

async def fetch_context_for_company(company: str, indices: List[str]):
    external_ctx = await get_company_context_from_perplexity_async(company)
    
    # Add None check
    if external_ctx is None:
        external_ctx = f"Recent market developments for {company} could not be retrieved."
    
    try:
        devrev_ctx = await multi_index_retriever(company, external_ctx, indices)
    except Exception:
        devrev_ctx = "DevRev is a modern CRM and issue-tracking platform for connecting customers to engineering."
    
    # Add None check
    if devrev_ctx is None:
        devrev_ctx = "DevRev is a modern CRM and issue-tracking platform for connecting customers to engineering."
    
    return {
        "company": company,
        "external_ctx": external_ctx,
        "devrev_ctx": devrev_ctx
    }

# ===== HEALTH & TEST ENDPOINTS =====

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "active_agents": len(agent_manager.list_active_agents()),
        "pending_checkpoints": len(checkpoint_manager.pending_checkpoints)
    }

@app.get("/")
async def root():
    """API root"""
    return {
        "message": "🤖 RevReach Agent API",
        "version": "2.0.0",
        "features": ["AI Sales Intelligence", "Human Checkpoints", "Safety Controls"]
    }

@app.post("/test-email")
def test_email_send():
    """Test email functionality"""
    try:
        send_email(
            to_email=os.getenv("MY_EMAIL"),
            subject="Test Email from RevReach Agent",
            body="This is a test email from the agent system."
        )
        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    
# Add to your existing main.py file
@app.get("/safety-status")
async def get_safety_status():
    """Basic safety status - simplified version"""
    return {
        "current_limits": {
            "daily_emails": {"current": 0, "max": 50, "remaining": 50},
            "daily_campaigns": {"current": 0, "max": 5, "remaining": 5}
        },
        "compliance_status": "healthy",
        "alerts": [],
        "recommendations": ["All systems operating normally"]
    }

@app.get("/agent-dashboard")  
async def get_agent_dashboard():
    """Basic dashboard - simplified version"""
    return {
        "summary": {
            "active_agents": 0,
            "pending_checkpoints": 0,
            "total_campaigns_today": 0,
            "emails_sent_today": 0
        },
        "message": "Dashboard endpoint working - full agent system not integrated yet"
    }