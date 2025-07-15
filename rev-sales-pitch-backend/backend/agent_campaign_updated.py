# agent_campaign_updated.py
import asyncio
import json
from typing import Dict, List, Any
from datetime import datetime
from agent_state import AgentStatus, AgentPlan, AgentAction, agent_manager, RiskLevel
from checkpoint_system import checkpoint_manager, CheckpointType
from risk_assessment import risk_assessor
from uuid import uuid4
import uuid
# Add these imports at the top
import os
import logging
import asyncio
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# Add your prompt templates
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

# Add the retry function
async def retry_llm_invoke(prompt: str, retries: int = 3, delay: float = 5):
    llm = ChatOpenAI(
        model="gpt-4", 
        temperature=0.2, 
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    for attempt in range(retries):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                logging.warning(f"⚠️ Rate limit hit. Retrying in {delay} seconds... (Attempt {attempt + 1})")
                await asyncio.sleep(delay)
            else:
                raise
    raise Exception("🚨 Exceeded retry limit for OpenAI LLM.")

# Import your existing functions
from email_utils import send_email

# Add fetch_context_for_company if missing
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

async def get_simple_context_for_testing(company: str):
    """Simple context for testing - no external API calls"""
    return {
        "company": company,
        "external_ctx": f"{company} is a leading company in their sector facing typical growth challenges.",
        "devrev_ctx": "DevRev helps companies connect customer feedback directly to engineering teams, enabling faster product iterations and better customer satisfaction."
    }
async def run_agent_campaign(sector: str, job_id: str, recipient_email: str):
    """Main agent campaign logic with checkpoints"""
    
    # Initialize agent
    agent = agent_manager.create_agent(job_id)
    agent.status = AgentStatus.PLANNING
    agent.current_step = "initializing"
    
    try:
        # PHASE 1: PLANNING
        print("🤖 Agent: Starting campaign planning...")
        agent.current_step = "planning"
        
        # Discover companies
        companies = await discover_companies_with_agent(agent, sector)
        
        # Create campaign plan
        plan_data = {
            'sector': sector,
            'companies': companies,
            'recipient_email': recipient_email,
            'estimated_duration': len(companies) * 10,  # 10 minutes per company
            'created_at': datetime.now().isoformat()
        }
        
        # Risk assessment
        risk_level, assessment = risk_assessor.assess_campaign_risk(companies, sector)
        
        # Create plan approval checkpoint
        checkpoint = checkpoint_manager.create_plan_approval_checkpoint(job_id, plan_data)
        
        print(f"🤖 Agent: Campaign plan created. Risk level: {risk_level.value}")
        print(f"🤖 Agent: Waiting for human approval... (Checkpoint ID: {checkpoint.checkpoint_id})")
        
        # Wait for plan approval
        await wait_for_checkpoint_approval(agent, checkpoint.checkpoint_id)
        
        # PHASE 2: CONTEXT GATHERING
        print("🤖 Agent: Plan approved! Starting context gathering...")
        agent.status = AgentStatus.EXECUTING
        agent.current_step = "gathering_context"
        
        contexts = await gather_context_with_agent(agent, companies)
        
        # PHASE 3: EMAIL GENERATION WITH CHECKPOINTS
        print("🤖 Agent: Generating personalized emails...")
        agent.current_step = "generating_emails"
        
        emails = {}
        for ctx in contexts:
            company = ctx['company']
            
            # Check if company is high-risk
            company_risk = risk_assessor.assess_company_risk(company, sector)
            if company_risk == RiskLevel.HIGH:
                checkpoint = checkpoint_manager.create_high_risk_company_checkpoint(
                    job_id, company, "High-profile company requires manual approval"
                )
                await wait_for_checkpoint_approval(agent, checkpoint.checkpoint_id)
            
            # Generate email
            email_content = await generate_email_with_agent(agent, ctx)
            
            # Create email preview checkpoint for medium/high risk
            email_risk, risk_factors = risk_assessor.assess_email_content_risk(email_content, company)
            if email_risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]:
                checkpoint = checkpoint_manager.create_email_preview_checkpoint(
                    job_id, company, email_content, ctx
                )
                await wait_for_checkpoint_approval(agent, checkpoint.checkpoint_id)
                
                # Check if email was modified
                resolved_checkpoint = next(
                    (cp for cp in agent.checkpoints 
                     if cp.checkpoint_id == checkpoint.checkpoint_id and cp.resolved_at), 
                    None
                )
                if resolved_checkpoint and resolved_checkpoint.human_decision == "modify":
                    # Use modified content if provided
                    email_content = resolved_checkpoint.data.get('modified_content', email_content)
            
            emails[company] = email_content
            
        # PHASE 4: BULK SEND APPROVAL
        print("🤖 Agent: All emails generated. Requesting send approval...")
        agent.current_step = "requesting_send_approval"
        
        checkpoint = checkpoint_manager.create_bulk_send_checkpoint(job_id, emails)
        await wait_for_checkpoint_approval(agent, checkpoint.checkpoint_id)
        
        # PHASE 5: EMAIL SENDING
        print("🤖 Agent: Send approved! Sending emails...")
        agent.current_step = "sending_emails"
        
        results = await send_emails_with_agent(agent, emails, recipient_email)
        
        # PHASE 6: COMPLETION
        print("🤖 Agent: Campaign completed successfully!")
        agent.current_step = "completed"
        agent.status = AgentStatus.COMPLETED
        
        # Store final results
        agent.context.update({
            'final_results': results,
            'total_emails': len(emails),
            'successful_sends': len([r for r in results if r['status'] == 'sent']),
            'completion_time': datetime.now().isoformat()
        })
        
        return {
            'status': 'completed',
            'results': results,
            'checkpoints_used': len(agent.checkpoints),
            'human_interventions': len([cp for cp in agent.checkpoints if cp.resolved_at])
        }
        
    except Exception as e:
        print(f"🤖 Agent: Error encountered: {str(e)}")
        
        # Create error intervention checkpoint
        checkpoint = checkpoint_manager.create_error_intervention_checkpoint(
            job_id, str(e), {'current_step': agent.current_step}
        )
        
        agent.status = AgentStatus.INTERVENTION_REQUIRED
        agent.fail(str(e))
        
        return {
            'status': 'failed',
            'error': str(e),
            'checkpoint_id': checkpoint.checkpoint_id
        }

async def wait_for_checkpoint_approval(agent, checkpoint_id: str, timeout: int = 300):
    """Wait for human approval on a checkpoint"""
    start_time = datetime.now()
    
    while True:
        # Check if checkpoint is resolved
        checkpoint = next(
            (cp for cp in agent.checkpoints if cp.checkpoint_id == checkpoint_id), 
            None
        )
        
        if checkpoint and checkpoint.resolved_at:
            decision = checkpoint.human_decision
            if decision == "approve":
                print(f"🤖 Agent: Checkpoint approved, continuing...")
                return True
            elif decision == "reject":
                print(f"🤖 Agent: Checkpoint rejected, stopping campaign...")
                raise Exception("Human rejected checkpoint")
            elif decision == "modify":
                print(f"🤖 Agent: Checkpoint approved with modifications...")
                return True
            else:
                print(f"🤖 Agent: Unknown decision: {decision}")
                raise Exception(f"Unknown checkpoint decision: {decision}")
        
        # Check timeout
        if (datetime.now() - start_time).seconds > timeout:
            raise Exception("Checkpoint approval timeout")
        
        # Wait before checking again
        await asyncio.sleep(2)

async def discover_companies_with_agent(agent, sector: str) -> List[str]:
    """Discover companies with agent tracking"""
    action = AgentAction(
        action_id=str(uuid.uuid4()),
        type="discover_companies",
        target=sector,
        status="started",
        started_at=datetime.now()
    )
    agent.add_action(action)
    
    try:
        # Your existing company discovery logic
        resp = await retry_llm_invoke(discover_prompt.format(sector=sector))
        companies = json.loads(resp.content.strip())
        companies = companies[:5]  # Limit for testing
        
        action.status = "completed"
        action.completed_at = datetime.now()
        
        print(f"🤖 Agent: Discovered {len(companies)} companies: {', '.join(companies)}")
        return companies
        
    except Exception as e:
        action.status = "failed"
        action.error = str(e)
        action.completed_at = datetime.now()
        raise

async def gather_context_with_agent(agent, companies: List[str]) -> List[Dict]:
    """Gather context with agent tracking"""
    contexts = []
    
    for i, company in enumerate(companies):
        print(f"🤖 Agent: Researching {company} ({i+1}/{len(companies)})...")
        
        action = AgentAction(
            action_id=str(uuid.uuid4()),
            type="gather_context",
            target=company,
            status="started",
            started_at=datetime.now()
        )
        agent.add_action(action)
        
        try:
            # Your existing context gathering logic
            context = await fetch_context_for_company(company, ["devrev-knowledge-hub"])
            contexts.append(context)
            
            action.status = "completed"
            action.completed_at = datetime.now()
            
        except Exception as e:
            action.status = "failed"
            action.error = str(e)
            action.completed_at = datetime.now()
            # Continue with other companies
            
    return contexts

async def generate_email_with_agent(agent, context: Dict) -> str:
    """Generate email with agent tracking"""
    company = context['company']
    
    action = AgentAction(
        action_id=str(uuid.uuid4()),
        type="generate_email",
        target=company,
        status="started",
        started_at=datetime.now()
    )
    agent.add_action(action)
    
    try:
        # Your existing email generation logic
        prompt = email_prompt.format(**context)
        resp = await retry_llm_invoke(prompt)
        email_content = resp.content
        
        action.status = "completed"
        action.completed_at = datetime.now()
        
        print(f"🤖 Agent: Generated email for {company}")
        return email_content
        
    except Exception as e:
        action.status = "failed"
        action.error = str(e)
        action.completed_at = datetime.now()
        raise

async def send_emails_with_agent(agent, emails: Dict[str, str], recipient_email: str) -> List[Dict]:
    """Send emails with agent tracking"""
    results = []
    
    for company, email_content in emails.items():
        print(f"🤖 Agent: Sending email to {company}...")
        
        action = AgentAction(
            action_id=str(uuid.uuid4()),
            type="send_email",
            target=company,
            status="started",
            started_at=datetime.now()
        )
        agent.add_action(action)
        
        try:
            # Your existing email sending logic
            subject = f"Opportunities for {company} with DevRev"
            send_email(to_email=recipient_email, subject=subject, body=email_content)
            
            action.status = "completed"
            action.completed_at = datetime.now()
            
            results.append({
                'company': company,
                'to': recipient_email,
                'status': 'sent',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            action.status = "failed"
            action.error = str(e)
            action.completed_at = datetime.now()
            
            results.append({
                'company': company,
                'to': recipient_email,
                'status': f'failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
            
    return results