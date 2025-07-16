# main.py - Fixed version based on your working code with approval system

import os
import uuid
import asyncio
import datetime
import json
import ast
import re
import httpx
import logging
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from database import persistent_agent_manager as agent_manager
from database import persistent_checkpoint_manager as checkpoint_manager
import signal
import asyncio
from functools import wraps


# Load environment variables
load_dotenv()

# Validate required environment variables
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

# LangChain imports - exactly as in your working code
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import ElasticsearchStore
from langchain.prompts import PromptTemplate

# Email utilities
from email_utils import send_email

app = FastAPI(title="RevReach Agent - DevRev Inspired")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def timeout_protection(timeout_seconds):
    """Decorator to add timeout protection to async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                print(f"❌ [TIMEOUT] {func.__name__} timed out after {timeout_seconds} seconds")
                return None
        return wrapper
    return decorator

# Your exact LangChain setup
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.getenv("OPENAI_API_KEY"))
embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

# Your exact prompt templates
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

DO NOT include placeholder text like [Your Name], [Your Title], or any bracketed placeholders.
DO NOT include a subject line in the email body.

Email:
""")
def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def with_timeout(timeout_seconds):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logging.error(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
                raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
        return wrapper
    return decorator

@timeout_protection(15)
async def get_company_context_from_perplexity_async(company: str) -> str:
    """Perplexity API with strict timeout"""
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "user", 
                "content": f"Brief 2-sentence summary of {company}'s recent challenges in 2024."
            }
        ],
        "max_tokens": 100,
        "temperature": 0.1
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions", 
                headers=headers, 
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return content or f"{company} continues to navigate growth challenges."
            else:
                print(f"❌ Perplexity API failed: {response.status_code}")
                return f"{company} continues to navigate growth challenges."
                
    except Exception as e:
        print(f"❌ Perplexity exception: {e}")
        return f"{company} continues to navigate growth challenges."

@timeout_protection(10)
async def get_company_context_from_openai_fallback(company: str) -> str:
    """OpenAI fallback with strict timeout"""
    try:
        llm = ChatOpenAI(
            model="gpt-4", 
            temperature=0.2, 
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            request_timeout=8
        )
        
        prompt = f"Brief 2-sentence summary of typical challenges for {company} in 2024."
        response = await llm.ainvoke(prompt)
        return response.content.strip()
        
    except Exception as e:
        print(f"❌ OpenAI fallback failed: {e}")
        return f"{company} faces typical industry challenges including market competition and operational efficiency."

@timeout_protection(20)
async def multi_index_retriever_with_timeout(company: str, external_ctx: str, indices: List[str]) -> str:
    """RAG retrieval with timeout protection"""
    try:
        docs = []
        for index in indices[:1]:  # Limit to just 1 index for speed
            try:
                store = ElasticsearchStore(
                    es_url=ES_URL,
                    index_name=index,
                    embedding=embedding_model,
                    es_user=os.getenv("ES_USERNAME"),
                    es_password=os.getenv("ES_PASSWORD"),
                )
                retriever = store.as_retriever(search_kwargs={"k": 2})  # Limit results
                docs += retriever.get_relevant_documents(f"{company} DevRev solution")
                break  # Exit after first successful index
            except Exception as e:
                print(f"❌ ES index {index} failed: {e}")
                continue
        
        if docs:
            return "\n\n".join([d.page_content for d in docs[:2]])  # Limit to 2 docs
        else:
            return "DevRev helps companies connect customer feedback to engineering teams for faster product iterations."
            
    except Exception as e:
        print(f"❌ RAG retrieval failed: {e}")
        return "DevRev helps companies connect customer feedback to engineering teams for faster product iterations."

@timeout_protection(15)
async def retry_llm_invoke_with_timeout(prompt: str) -> str:
    """LLM invoke with timeout and single retry"""
    try:
        llm = ChatOpenAI(
            model="gpt-4", 
            temperature=0.2, 
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            request_timeout=10
        )
        
        response = await llm.ainvoke(prompt)
        return response.content
        
    except Exception as e:
        print(f"❌ LLM invoke failed: {e}")
        # Return fallback email
        return """Dear Team,

I hope this email finds you well. I'm reaching out from DevRev to discuss how we can help enhance your customer engagement and product development processes.

DevRev offers an integrated platform that connects customer feedback directly to engineering teams, enabling faster product iterations and better customer satisfaction.

Would you be open to a brief conversation about how DevRev can support your growth objectives?

Best regards,
John Doe
DevRev Sales Team"""

async def get_company_context_from_perplexity_async(company: str) -> str:
    """Try Perplexity first, fallback to OpenAI if it fails"""
    
    # First try Perplexity
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        # Simplified payload - removing problematic fields
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a helpful assistant that provides concise business intelligence."
                },
                {
                    "role": "user", 
                    "content": f"Provide a brief 2-sentence summary of recent business challenges or developments for {company} in 2024."
                }
            ],
            "max_tokens": 150,
            "temperature": 0.1
            # Removed search filters that might cause 400
        }
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            print(f"🔍 [DEBUG] Trying Perplexity API for {company}")
            
            response = await client.post(
                "https://api.perplexity.ai/chat/completions", 
                headers=headers, 
                json=payload
            )
            
            print(f"🔍 [DEBUG] Perplexity response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    print(f"✅ [DEBUG] Perplexity success for {company}")
                    return content
            else:
                print(f"❌ [DEBUG] Perplexity failed: {response.status_code} - {response.text}")
                raise Exception(f"Perplexity API failed with {response.status_code}")
                
    except Exception as e:
        print(f"❌ [DEBUG] Perplexity failed for {company}: {e}")
        print(f"🔄 [DEBUG] Falling back to OpenAI for {company}")
        
        # Fallback to OpenAI
        try:
            return await get_company_context_from_openai(company)
        except Exception as openai_error:
            print(f"❌ [DEBUG] OpenAI fallback also failed for {company}: {openai_error}")
            return f"Recent market developments for {company} could not be retrieved, but the company continues to operate in the {company.split()[0] if company.split() else 'technology'} sector."


async def get_company_context_from_openai(company: str) -> str:
    """OpenAI fallback for company context"""
    try:
        llm = ChatOpenAI(
            model="gpt-4", 
            temperature=0.2, 
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        prompt = f"""
        You are a business intelligence assistant. Provide a brief 2-sentence summary of recent business challenges, developments, or strategic initiatives for {company} in 2024. 
        Focus on realistic business challenges that a B2B company like {company} might face.
        If you don't have specific recent information, provide plausible industry-typical challenges.
        
        Company: {company}
        """
        
        response = await asyncio.wait_for(
            llm.ainvoke(prompt),
            timeout=15.0
        )
        
        content = response.content.strip()
        print(f"✅ [DEBUG] OpenAI fallback success for {company}")
        return content
        
    except Exception as e:
        print(f"❌ [DEBUG] OpenAI fallback failed for {company}: {e}")
        return f"{company} is navigating typical growth challenges in their sector, including customer acquisition costs and market competition. The company continues to focus on product development and customer satisfaction initiatives."

async def multi_index_retriever(company: str, external_ctx: str, indices: List[str]) -> str:
    docs = []
    for index in indices:
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

    seen, unique_docs = set(), []
    for d in docs:
        if d.page_content not in seen:
            seen.add(d.page_content)
            unique_docs.append(d)
    return "\n\n".join([d.page_content for d in unique_docs])

async def fetch_context_for_company(company: str, indices: List[str]):
    external_ctx = await get_company_context_from_perplexity_async(company)
    try:
        devrev_ctx = await multi_index_retriever(company, external_ctx, indices)
    except Exception:
        devrev_ctx = "DevRev is a modern CRM and issue-tracking platform for connecting customers to engineering."
    return {
        "company": company,
        "external_ctx": external_ctx,
        "devrev_ctx": devrev_ctx
    }

def extract_subject_and_body(email_text: str):
    """Fixed: Extracts subject and ensures it's not left in body"""
    subject_match = re.search(r'^Subject:\s*(.*)', email_text, re.MULTILINE)
    subject = subject_match.group(1).strip() if subject_match else None

    # Remove the subject line from the body completely
    if subject:
        email_text = re.sub(r'^Subject:.*\n?', '', email_text, flags=re.MULTILINE).strip()
    
    return subject, email_text

async def retry_llm_invoke(prompt: str, retries: int = 3, delay: float = 5):
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

# Models for our approval system
class AgentCampaignRequest(BaseModel):
    sector: str
    recipient_email: EmailStr
    autonomy_level: str = "supervised"

class CheckpointDecision(BaseModel):
    checkpoint_id: str
    decision: str
    feedback: Optional[str] = None
    selected_companies: Optional[List[str]] = None
    selected_emails: Optional[List[str]] = None

# Email tracking database
class EmailDatabase:
    def __init__(self, db_file="sent_emails.json"):
        self.db_file = db_file
        self.load_db()
    
    def load_db(self):
        try:
            with open(self.db_file, 'r') as f:
                self.emails = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.emails = []
    
    def save_db(self):
        with open(self.db_file, 'w') as f:
            json.dump(self.emails, f, indent=2)
    
    def add_sent_email(self, sector: str, company: str, email_content: str, recipient: str, status: str = "sent"):
        email_record = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.datetime.now().isoformat(),
            "date": datetime.date.today().isoformat(),
            "sector": sector,
            "company": company,
            "recipient": recipient,
            "email_content": email_content,
            "status": status,
            "email_length": len(email_content),
            "sophisticated": True  # Mark as sophisticated email
        }
        self.emails.append(email_record)
        self.save_db()
        return email_record
    
    def get_emails_today(self):
        today = datetime.date.today().isoformat()
        return [email for email in self.emails if email.get("date") == today]
    
    def get_analytics(self):
        today_emails = self.get_emails_today()
        sectors = {}
        companies = set()
        
        for email in today_emails:
            sector = email.get("sector", "Unknown")
            if sector not in sectors:
                sectors[sector] = 0
            sectors[sector] += 1
            companies.add(email.get("company"))
        
        return {
            "total_emails_today": len(today_emails),
            "unique_companies_today": len(companies),
            "sectors_today": sectors,
            "total_emails_all_time": len(self.emails),
            "recent_emails": today_emails[-20:]
        }

email_db = EmailDatabase()

# Company databases by sector - using your exact logic but expanded
SECTOR_COMPANIES = {
    "SaaS": ["Slack Technologies", "Notion Labs", "Linear", "Figma Inc", "Webflow"],
    "FinTech": ["Stripe Inc", "Square Inc", "Plaid Technologies", "Coinbase Inc", "Robinhood"],
    "Healthcare": ["Teladoc Health", "23andMe", "Moderna Inc", "Guardant Health", "10x Genomics"],
    "E-commerce": ["Shopify Inc", "BigCommerce", "WooCommerce", "Magento Commerce", "PrestaShop"],
    "EdTech": ["Coursera Inc", "Udemy Inc", "Khan Academy", "Chegg Inc", "Duolingo"],
    "CleanTech": ["Tesla Energy", "SolarCity Corp", "Beyond Meat", "ChargePoint Inc", "Bloom Energy"]
}

# Risk assessment
COMPANY_RISK_DATA = {
    "Slack Technologies": {"risk": "HIGH", "reason": "Major enterprise platform with strict vendor policies"},
    "Figma Inc": {"risk": "HIGH", "reason": "Recently acquired by Adobe, complex decision-making"},
    "Tesla Energy": {"risk": "HIGH", "reason": "Elon Musk company with unique communication preferences"},
    "Stripe Inc": {"risk": "HIGH", "reason": "Major financial infrastructure company with compliance focus"},
    "Moderna Inc": {"risk": "HIGH", "reason": "Pharmaceutical company with regulatory considerations"},
}

def get_company_risk_info(company: str):
    if company in COMPANY_RISK_DATA:
        return COMPANY_RISK_DATA[company]
    else:
        return {"risk": "LOW", "reason": "Standard business prospect, no special considerations"}

# Simple agent system for approval flow
class SimpleAgent:
    def __init__(self, job_id):
        self.job_id = job_id
        self.status = "planning"
        self.current_step = "initializing"
        self.progress = 0
        self.checkpoints = []
        self.created_at = datetime.datetime.now()
        self.sector = None
        self.autonomy_level = "supervised"
        self.selected_companies = []
        self.recipient_email = None
        self.contexts = []
        self.generated_emails = {}
    
    def update_progress(self):
        progress_map = {
            "initializing": 5,
            "planning": 15,
            "fetching_contexts": 35,
            "generating_emails": 60,
            "requesting_send_approval": 80,
            "sending_emails": 95,
            "completed": 100
        }
        self.progress = progress_map.get(self.current_step, 0)

class SimpleCheckpoint:
    def __init__(self, checkpoint_id, checkpoint_type, data, message):
        self.checkpoint_id = checkpoint_id
        self.type = checkpoint_type
        self.data = data
        self.message = message
        self.risk_level = "medium"
        self.requires_approval = True
        self.created_at = datetime.datetime.now()
        self.resolved_at = None
        self.human_decision = None

class SimpleAgentManager:
    def __init__(self):
        self.agents = {}
    
    def create_agent(self, job_id):
        agent = SimpleAgent(job_id)
        self.agents[job_id] = agent
        return agent
    
    def get_agent(self, job_id):
        return self.agents.get(job_id)
    
    def list_active_agents(self):
        return [agent for agent in self.agents.values() if agent.status not in ['completed', 'failed']]

class SimpleCheckpointManager:
    def __init__(self):
        self.pending_checkpoints = {}
        self.checkpoint_counter = 0
    
    def create_checkpoint(self, job_id, checkpoint_type, data, message):
        self.checkpoint_counter += 1
        checkpoint_id = f"checkpoint_{self.checkpoint_counter}"
        
        checkpoint = SimpleCheckpoint(checkpoint_id, checkpoint_type, data, message)
        self.pending_checkpoints[checkpoint_id] = checkpoint
        
        agent = agent_manager.get_agent(job_id)
        if agent:
            agent.checkpoints.append(checkpoint)
            if agent.autonomy_level == "supervised":
                agent.status = "waiting_approval"
            else:
                asyncio.create_task(self.auto_approve_checkpoint(checkpoint_id, agent))
        
        return checkpoint
    
    async def auto_approve_checkpoint(self, checkpoint_id, agent):
        checkpoint = self.pending_checkpoints.get(checkpoint_id)
        if not checkpoint:
            return
            
        if checkpoint.type == "plan_approval":
            companies = checkpoint.data.get('companies', [])
            agent.selected_companies = companies
            self.resolve_checkpoint(checkpoint_id, "approve", "Auto-approved all companies")
            await self.auto_generate_emails_for_agent(agent)
            
        elif checkpoint.type == "email_preview":
            emails = checkpoint.data.get('emails', {})
            agent.selected_emails = list(emails.keys())
            self.resolve_checkpoint(checkpoint_id, "approve", "Auto-approved all emails")
            await self.auto_create_send_checkpoint(agent)
            
        elif checkpoint.type == "bulk_send_approval":
            await self.auto_send_emails_and_complete(agent, checkpoint)
    
    async def auto_generate_emails_for_agent(self, agent):
        try:
            agent.status = "executing"
            agent.current_step = "fetching_contexts"
            agent.update_progress()
            
            # Use your exact context fetching logic
            indices = ["devrev-knowledge-hub", "devrev_yt_100", "devrev_docs_casestudies"]
            semaphore = asyncio.Semaphore(1)
            
            async def throttled_context_fetch(company):
                async with semaphore:
                    return await fetch_context_for_company(company, indices)
            
            context_tasks = [throttled_context_fetch(c) for c in agent.selected_companies]
            contexts = await asyncio.gather(*context_tasks)
            agent.contexts = contexts
            
            agent.current_step = "generating_emails"
            agent.update_progress()
            
            emails = {}
            for ctx in contexts:
                prompt = email_prompt.format(**ctx)
                resp = await retry_llm_invoke(prompt)
                emails[ctx["company"]] = resp.content
                
            agent.generated_emails = emails
            
            email_data = {
                "emails": emails,
                "total_steps": 3,
                "current_step": 2,
                "sector": agent.sector,
                "recipient_email": agent.recipient_email
            }
            
            self.create_checkpoint(agent.job_id, "email_preview", email_data, 
                                 f"Auto-generated {len(emails)} emails for {agent.sector} companies")
                                 
        except Exception as e:
            agent.status = "failed"
            logging.error(f"Auto email generation failed: {e}")
    
    async def auto_create_send_checkpoint(self, agent):
        try:
            agent.current_step = "requesting_send_approval"
            agent.update_progress()
            
            send_data = {
                "emails": agent.generated_emails,
                "total_steps": 3,
                "current_step": 3,
                "sector": agent.sector,
                "recipient_email": agent.recipient_email
            }
            
            self.create_checkpoint(agent.job_id, "bulk_send_approval", send_data,
                                 f"Auto-sending {len(agent.generated_emails)} emails to {agent.sector} companies")
                                 
        except Exception as e:
            agent.status = "failed"
            logging.error(f"Auto send checkpoint creation failed: {e}")
    
    async def auto_send_emails_and_complete(self, agent, checkpoint):
        try:
            emails = checkpoint.data.get('emails', {})
            recipient_email = checkpoint.data.get('recipient_email') or agent.recipient_email
            
            self.resolve_checkpoint(checkpoint.checkpoint_id, "approve", "Auto-approved send")
            
            agent.current_step = "sending_emails"
            agent.update_progress()
            
            results = []
            for company, raw_body in emails.items():
                # Use your exact email processing logic
                subject_extracted, email_body = extract_subject_and_body(raw_body)
                subject = subject_extracted or f"DevRev Partnership Opportunity for {company}"
                
                # Your exact signature and cleaning logic
                signature = "\n\nBest regards,\nJohn Doe\nDevRev Sales Team"
                
                placeholder_patterns = [
                    r"(?i)^looking forward to.*",
                    r"(?i)^best( regards)?,?.*",
                    r"(?i)^\[.*\]$",
                    r"(?i)^insert.*",
                    r"(?i)^devrev.*",
                    r"(?i)\[your.*?\]",  # Additional pattern for [Your Name] etc
                    r"(?i)\{your.*?\}",  # Pattern for {Your Name} etc
                ]
                
                email_lines = email_body.strip().splitlines()
                cleaned_lines = []
                for line in email_lines:
                    line_clean = line.strip()
                    if any(re.search(pat, line_clean) for pat in placeholder_patterns):
                        continue
                    cleaned_lines.append(line)
                cleaned_body = "\n".join(cleaned_lines).strip()
                
                full_body = cleaned_body + signature
                
                try:
                    send_email(to_email=recipient_email, subject=subject, body=full_body)
                    results.append({"company": company, "to": recipient_email, "status": "sent"})
                    
                    email_db.add_sent_email(
                        sector=agent.sector,
                        company=company,
                        email_content=full_body,
                        recipient=recipient_email,
                        status="sent"
                    )
                    
                except Exception as e:
                    error_msg = f"failed: {str(e)}"
                    results.append({"company": company, "to": recipient_email, "status": error_msg})
                    
                    email_db.add_sent_email(
                        sector=agent.sector,
                        company=company,
                        email_content=full_body,
                        recipient=recipient_email,
                        status=error_msg
                    )
            
            agent.status = "completed"
            agent.current_step = "completed"
            agent.progress = 100
            
        except Exception as e:
            agent.status = "failed"
            logging.error(f"Auto email sending failed: {e}")
    
    def get_pending_checkpoints(self, job_id):
        agent = agent_manager.get_agent(job_id)
        if agent:
            return [cp for cp in agent.checkpoints if cp.resolved_at is None]
        return []
    
    def resolve_checkpoint(self, checkpoint_id, decision, feedback):
        if checkpoint_id in self.pending_checkpoints:
            checkpoint = self.pending_checkpoints[checkpoint_id]
            checkpoint.resolved_at = datetime.datetime.now()
            checkpoint.human_decision = decision
            
            for agent in agent_manager.agents.values():
                for i, cp in enumerate(agent.checkpoints):
                    if cp.checkpoint_id == checkpoint_id:
                        agent.checkpoints[i].resolved_at = checkpoint.resolved_at
                        agent.checkpoints[i].human_decision = decision
                        break
            
            del self.pending_checkpoints[checkpoint_id]
            return True
        return False



async def run_enhanced_campaign(sector: str, job_id: str, recipient_email: str, autonomy_level: str):
    agent = agent_manager.get_agent(job_id)
    if not agent:
        return {"status": "failed", "error": "Agent not found"}
    
    agent.sector = sector
    agent.autonomy_level = autonomy_level
    agent.recipient_email = recipient_email
    agent.save() 
    
    try:
        print(f"🚀 [DEBUG] Starting campaign - Job ID: {job_id}, Autonomy: {autonomy_level}")
        
        # Simple company discovery using existing sector companies
        companies = SECTOR_COMPANIES.get(sector, [])[:3]  # Use predefined companies
        
        print(f"✅ [DEBUG] Companies discovered: {companies}")
        
        # Create companies with risk assessment
        companies_with_risk = []
        for company in companies:
            risk_info = get_company_risk_info(company)
            companies_with_risk.append({
                "name": company,
                "risk_level": risk_info["risk"],
                "risk_reason": risk_info["reason"]
            })
        
        # Create plan data
        plan_data = {
            "sector": sector,
            "companies": companies,
            "companies_with_risk": companies_with_risk,
            "recipient_email": recipient_email,
            "total_steps": 3,
            "current_step": 1
        }
        
        print(f"🔍 [DEBUG] Agent autonomy level: {agent.autonomy_level}")
        print(f"🔍 [DEBUG] Creating checkpoint for job_id: {job_id}")
        
        # Create checkpoint
        checkpoint = checkpoint_manager.create_checkpoint(
            job_id, 
            "plan_approval", 
            plan_data, 
            f"Review campaign plan for {sector} sector with {len(companies)} companies"
        )
        
        print(f"✅ [DEBUG] Checkpoint created: {checkpoint.checkpoint_id}")
        print(f"✅ [DEBUG] Agent status after checkpoint: {agent.status}")
        
        return {"status": "checkpoint_created", "companies": companies}
        
    except Exception as e:
        print(f"❌ [ERROR] Campaign failed: {str(e)}")
        agent.status = "failed"
        return {"status": "failed", "error": str(e)}

# API Endpoints
@app.post("/start-agent-campaign")
async def start_agent_campaign(request: AgentCampaignRequest):
    if request.autonomy_level not in ["supervised", "automatic"]:
        raise HTTPException(status_code=400, detail="Invalid autonomy level")
    
    job_id = str(uuid.uuid4())
    agent = agent_manager.create_agent(job_id)
    
    if request.sector not in SECTOR_COMPANIES:
        available_sectors = list(SECTOR_COMPANIES.keys())
        raise HTTPException(status_code=400, detail=f"Invalid sector. Available: {available_sectors}")
    
    asyncio.create_task(run_enhanced_campaign(
        sector=request.sector,
        job_id=job_id,
        recipient_email=request.recipient_email,
        autonomy_level=request.autonomy_level
    ))
    
    return {
        "message": f"🤖 Campaign started for {request.sector}",
        "job_id": job_id,
        "agent_status": agent.status,
        "autonomy_level": request.autonomy_level,
        "sector": request.sector
    }

@app.post("/approve-checkpoint")
async def approve_checkpoint(decision: CheckpointDecision):
    checkpoint_id = decision.checkpoint_id
    
    # Use the new database method to get checkpoint
    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    # Check if checkpoint is already resolved
    if checkpoint.resolved_at:
        raise HTTPException(status_code=400, detail="Checkpoint already resolved")
    
    # Get the agent
    agent = agent_manager.get_agent(checkpoint.job_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if decision.decision == "approve":
        # Resolve the checkpoint
        success = checkpoint_manager.resolve_checkpoint(checkpoint_id, "approve", decision.feedback or "Approved")
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to resolve checkpoint")
        
        if checkpoint.type == "plan_approval":
            selected_companies = decision.selected_companies or checkpoint.data.get('companies', [])
            agent.selected_companies = selected_companies
            agent.status = "executing"
            agent.current_step = "fetching_contexts"
            agent.update_progress()
            
            asyncio.create_task(generate_sophisticated_emails_for_agent(agent))
            message = f"✅ Plan approved! Generating {len(selected_companies)} sophisticated emails..."
            
        elif checkpoint.type == "email_preview":
            all_emails = checkpoint.data.get('emails', {})
            selected_email_companies = decision.selected_emails or list(all_emails.keys())
            
            selected_emails = {company: all_emails[company] for company in selected_email_companies if company in all_emails}
            
            agent.status = "executing"
            agent.current_step = "requesting_send_approval"
            agent.update_progress()
            
            send_data = {
                "emails": selected_emails,
                "total_steps": 3,
                "current_step": 3,
                "sector": agent.sector,
                "recipient_email": agent.recipient_email
            }
            
            checkpoint_manager.create_checkpoint(
                agent.job_id, "bulk_send_approval", send_data,
                f"Ready to send {len(selected_emails)} emails to {agent.sector} companies"
            )
            
            message = f"✅ Emails approved! Ready to send {len(selected_emails)} selected emails"
            
        elif checkpoint.type == "bulk_send_approval":
            asyncio.create_task(send_sophisticated_emails_for_agent(agent, checkpoint))
            message = f"✅ Sending emails using sophisticated system..."
            
        else:
            message = "✅ Checkpoint approved"
            
    elif decision.decision == "reject":
        checkpoint_manager.resolve_checkpoint(checkpoint_id, "reject", decision.feedback or "Rejected")
        agent.status = "failed"
        agent.current_step = "cancelled"
        agent.save()  # Save the updated agent status
        message = "❌ Campaign cancelled"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")
    
    return {
        "message": message,
        "checkpoint_id": checkpoint_id,
        "decision": decision.decision,
        "agent_status": agent.status,
        "timestamp": datetime.datetime.now().isoformat(),
        "refresh_needed": True
    }

@with_timeout(120)
async def generate_sophisticated_emails_for_agent(agent):
    """Generate emails with aggressive timeouts and fallbacks"""
    try:
        print(f"🚀 [DEBUG] Starting fast email generation for agent {agent.job_id}")
        
        agent.status = "executing"
        agent.current_step = "generating_emails"
        agent.update_progress()
        
        emails = {}
        
        # Process companies in parallel with timeout
        async def generate_single_email(company):
            try:
                print(f"🔍 [DEBUG] Generating email for {company}")
                
                # Try Perplexity first (with timeout)
                external_ctx = await get_company_context_from_perplexity_async(company)
                if not external_ctx:
                    # Fallback to OpenAI
                    external_ctx = await get_company_context_from_openai_fallback(company)
                    if not external_ctx:
                        external_ctx = f"{company} continues to navigate growth challenges in their sector."
                
                # Try RAG retrieval (with timeout)
                indices = ["devrev-knowledge-hub"]  # Just 1 index for speed
                devrev_ctx = await multi_index_retriever_with_timeout(company, external_ctx, indices)
                if not devrev_ctx:
                    devrev_ctx = "DevRev helps companies connect customer feedback to engineering teams."
                
                # Generate email (with timeout)
                context = {
                    "company": company,
                    "external_ctx": external_ctx,
                    "devrev_ctx": devrev_ctx
                }
                
                prompt = email_prompt.format(**context)
                email_content = await retry_llm_invoke_with_timeout(prompt)
                
                print(f"✅ [DEBUG] Email generated for {company}")
                return company, email_content
                
            except Exception as e:
                print(f"❌ [DEBUG] Email generation failed for {company}: {e}")
                # Fallback email
                fallback_email = f"""Dear {company} Team,

I hope this email finds you well. I'm reaching out from DevRev to discuss how we can help {company} enhance customer engagement and product development processes.

DevRev offers an integrated platform that connects customer feedback directly to engineering teams, enabling faster product iterations and better customer satisfaction.

Would you be open to a brief conversation about how DevRev can support {company}'s growth objectives?

Best regards,
John Doe
DevRev Sales Team"""
                return company, fallback_email
        
        # Process all companies concurrently with overall timeout
        try:
            tasks = [generate_single_email(company) for company in agent.selected_companies]
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=120)  # 2 minute total timeout
            
            for company, email_content in results:
                emails[company] = email_content
                
        except asyncio.TimeoutError:
            print(f"❌ [DEBUG] Overall email generation timed out, using fallbacks")
            # Generate fallback emails for any missing companies
            for company in agent.selected_companies:
                if company not in emails:
                    emails[company] = f"""Dear {company} Team,

I hope this email finds you well. I'm reaching out from DevRev to discuss partnership opportunities.

DevRev offers an integrated platform that connects customer feedback directly to engineering teams.

Would you be open to a brief conversation?

Best regards,
John Doe
DevRev Sales Team"""
        
        agent.generated_emails = emails
        agent.save()
        
        print(f"✅ [DEBUG] All emails generated for agent {agent.job_id}")
        
        # Create email preview checkpoint
        email_data = {
            "emails": emails,
            "total_steps": 3,
            "current_step": 2,
            "sector": agent.sector,
            "recipient_email": agent.recipient_email
        }
        
        checkpoint_manager.create_checkpoint(agent.job_id, "email_preview", email_data, 
                                           f"Review {len(emails)} emails for {agent.sector} companies")
        
        print(f"✅ [DEBUG] Email preview checkpoint created for agent {agent.job_id}")
                                           
    except Exception as e:
        print(f"❌ [DEBUG] Overall email generation failed for agent {agent.job_id}: {e}")
        agent.status = "failed"
        agent.save()
        logging.error(f"Email generation failed: {e}")

async def send_sophisticated_emails_for_agent(agent, checkpoint):
    try:
        emails = checkpoint.data.get('emails', {})
        recipient_email = checkpoint.data.get('recipient_email') or agent.recipient_email
        
        if not recipient_email:
            raise ValueError("Recipient email is missing")
            
        agent.current_step = "sending_emails"
        agent.update_progress()
        
        results = []
        for company, raw_body in emails.items():
            # Your exact email processing logic with fixes
            subject_extracted, email_body = extract_subject_and_body(raw_body)
            subject = subject_extracted or f"DevRev Partnership Opportunity for {company}"
            
            # Enhanced signature
            signature = "\n\nBest regards,\nJohn Doe\nDevRev Sales Team"
            
            # Enhanced placeholder patterns
            placeholder_patterns = [
                r"(?i)^looking forward to.*",
                r"(?i)^best( regards)?,?.*",
                r"(?i)^\[.*\]$",
                r"(?i)^insert.*",
                r"(?i)^devrev.*(?:team|sales)",
                r"(?i)\[your.*?\]",
                r"(?i)\{your.*?\}",
                r"(?i)\[.*name.*\]",
                r"(?i)\{.*name.*\}",
                r"(?i)\[.*title.*\]",
                r"(?i)\{.*title.*\}",
            ]
            
            email_lines = email_body.strip().splitlines()
            cleaned_lines = []
            for line in email_lines:
                line_clean = line.strip()
                if any(re.search(pat, line_clean) for pat in placeholder_patterns):
                    continue
                cleaned_lines.append(line)
            cleaned_body = "\n".join(cleaned_lines).strip()
            
            full_body = cleaned_body + signature
            
            try:
                send_email(to_email=recipient_email, subject=subject, body=full_body)
                results.append({"company": company, "to": recipient_email, "status": "sent"})
                
                email_db.add_sent_email(
                    sector=agent.sector,
                    company=company,
                    email_content=full_body,
                    recipient=recipient_email,
                    status="sent"
                )
                
                print(f"✅ Sophisticated email sent to {company} ({recipient_email})")
                
            except Exception as e:
                error_msg = f"failed: {str(e)}"
                results.append({"company": company, "to": recipient_email, "status": error_msg})
                
                email_db.add_sent_email(
                    sector=agent.sector,
                    company=company,
                    email_content=full_body,
                    recipient=recipient_email,
                    status=error_msg
                )
                
                print(f"❌ Failed to send to {company}: {str(e)}")
        
        agent.status = "completed"
        agent.current_step = "completed"
        agent.progress = 100
        
        sent = sum(1 for r in results if r["status"] == "sent")
        print(f"📊 Sophisticated Email Results: Sent = {sent}, Failed = {len(results) - sent}")
        
    except Exception as e:
        agent.status = "failed"
        logging.error(f"Sophisticated email sending failed: {e}")

@app.get("/agent-status/{job_id}")
async def get_agent_status(job_id: str):
    agent = agent_manager.get_agent(job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    pending_checkpoints = checkpoint_manager.get_pending_checkpoints(job_id)
    
    return {
        "job_id": job_id,
        "agent_status": agent.status,
        "current_step": agent.current_step,
        "progress": agent.progress,
        "sector": agent.sector,
        "autonomy_level": agent.autonomy_level,
        "selected_companies": agent.selected_companies,
        "agent_message": f"Agent is {agent.status}",
        "pending_checkpoints": [
            {
                "checkpoint_id": cp.checkpoint_id,
                "type": cp.type,
                "message": cp.message,
                "risk_level": cp.risk_level,
                "requires_approval": cp.requires_approval,
                "created_at": cp.created_at.isoformat(),
                "data": cp.data
            }
            for cp in pending_checkpoints
        ]
    }

@app.get("/agent-dashboard")
async def get_agent_dashboard():
    active_agents = agent_manager.list_active_agents()
    all_agents = agent_manager.get_all_agents()  # Use get_all_agents() instead of .agents
    
    # Get all pending checkpoints
    all_pending = []
    for agent in active_agents:
        pending = checkpoint_manager.get_pending_checkpoints(agent.job_id)
        all_pending.extend(pending)
    
    analytics = email_db.get_analytics()
    
    return {
        "summary": {
            "active_agents": len(active_agents),
            "pending_checkpoints": len(all_pending),
            "emails_sent_today": analytics["total_emails_today"],
            "total_campaigns_today": len(all_agents)  # Fixed this line
        },
        "active_agents": [
            {
                "job_id": agent.job_id,
                "status": agent.status,
                "current_step": agent.current_step,
                "progress": agent.progress,
                "sector": agent.sector,
                "autonomy_level": agent.autonomy_level,
                "pending_checkpoints": len(checkpoint_manager.get_pending_checkpoints(agent.job_id)),
                "created_at": agent.created_at.isoformat()
            }
            for agent in active_agents
        ]
    }

@app.get("/analytics")
async def get_analytics():
    analytics = email_db.get_analytics()
    
    today_emails = email_db.get_emails_today()
    
    sector_breakdown = {}
    company_breakdown = {}
    
    for email in today_emails:
        sector = email.get("sector", "Unknown")
        company = email.get("company", "Unknown")
        
        if sector not in sector_breakdown:
            sector_breakdown[sector] = {"count": 0, "companies": set()}
        sector_breakdown[sector]["count"] += 1
        sector_breakdown[sector]["companies"].add(company)
        
        if company not in company_breakdown:
            company_breakdown[company] = {"sector": sector, "emails": 0}
        company_breakdown[company]["emails"] += 1
    
    for sector_data in sector_breakdown.values():
        sector_data["companies"] = list(sector_data["companies"])
    
    return {
        "summary": analytics,
        "today_breakdown": {
            "by_sector": sector_breakdown,
            "by_company": company_breakdown
        },
        "recent_emails": today_emails
    }

@app.get("/analytics/filter")
async def get_filtered_analytics(sector: Optional[str] = None, date: Optional[str] = None):
    emails = email_db.emails
    
    if date:
        emails = [email for email in emails if email.get("date") == date]
    else:
        today = datetime.date.today().isoformat()
        emails = [email for email in emails if email.get("date") == today]
    
    if sector:
        emails = [email for email in emails if email.get("sector") == sector]
    
    return {
        "filtered_emails": emails,
        "count": len(emails),
        "unique_companies": len(set(email.get("company") for email in emails)),
        "filters_applied": {
            "sector": sector,
            "date": date or "today"
        }
    }

@app.get("/health")
async def health_check():
    analytics = email_db.get_analytics()
    return {
        "status": "healthy", 
        "timestamp": datetime.datetime.now().isoformat(),
        "emails_sent_today": analytics["total_emails_today"]
    }

@app.get("/")
async def root():
    return {"message": "🤖 RevReach Agent API - DevRev Inspired"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.post("/debug/cleanup")
async def cleanup_database():
    """Cleanup database for testing"""
    if os.getenv("ENVIRONMENT") != "production":
        import os
        db_path = "revreach_agents.db"
        if os.path.exists(db_path):
            os.remove(db_path)
        
        # Reinitialize database
        from database import db_manager
        db_manager.init_database()
        
        return {"message": "Database cleaned up"}
    else:
        return {"error": "Not allowed in production"}
    
@app.get("/agent-dashboard")
async def get_agent_dashboard():
    active_agents = agent_manager.list_active_agents()
    all_agents = agent_manager.get_all_agents()  # Get all agents for total count
    
    # Get all pending checkpoints
    all_pending = checkpoint_manager.get_all_pending_checkpoints()
    
    # Get analytics
    analytics = email_db.get_analytics()
    
    return {
        "summary": {
            "active_agents": len(active_agents),
            "pending_checkpoints": len(all_pending),
            "emails_sent_today": analytics["total_emails_today"],
            "total_campaigns_today": len(agent_manager.get_all_agents())
        },
        "active_agents": [
            {
                "job_id": agent.job_id,
                "status": agent.status,
                "current_step": agent.current_step,
                "progress": agent.progress,
                "sector": agent.sector,
                "autonomy_level": agent.autonomy_level,
                "pending_checkpoints": len(checkpoint_manager.get_pending_checkpoints(agent.job_id)),
                "created_at": agent.created_at.isoformat()
            }
            for agent in active_agents
        ]
    }

@app.get("/debug/all-agents")
async def debug_all_agents():
    all_agents = agent_manager.get_all_agents()
    return {
        "total_agents": len(all_agents),
        "agents": [
            {
                "job_id": agent.job_id,
                "status": agent.status,
                "created_at": agent.created_at.isoformat(),
                "autonomy_level": agent.autonomy_level
            }
            for agent in all_agents
        ]
    }

@app.get("/debug/test-apis/{company}")
async def test_apis(company: str):
    """Test both Perplexity and OpenAI APIs"""
    results = {}
    
    # Test Perplexity
    try:
        perplexity_result = await get_company_context_from_perplexity_async(company)
        results["perplexity"] = {
            "status": "success",
            "content": perplexity_result[:100] + "..." if len(perplexity_result) > 100 else perplexity_result
        }
    except Exception as e:
        results["perplexity"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Test OpenAI
    try:
        openai_result = await get_company_context_from_openai(company)
        results["openai"] = {
            "status": "success", 
            "content": openai_result[:100] + "..." if len(openai_result) > 100 else openai_result
        }
    except Exception as e:
        results["openai"] = {
            "status": "failed",
            "error": str(e)
        }
    
    return results

@app.get("/debug/campaign/{job_id}")
async def debug_campaign(job_id: str):
    """Debug a specific campaign"""
    agent = agent_manager.get_agent(job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get detailed agent information
    pending_checkpoints = checkpoint_manager.get_pending_checkpoints(job_id)
    
    debug_info = {
        "job_id": job_id,
        "agent_status": agent.status,
        "current_step": agent.current_step,
        "progress": agent.progress,
        "sector": agent.sector,
        "selected_companies": agent.selected_companies,
        "pending_checkpoints": len(pending_checkpoints),
        "checkpoint_details": [
            {
                "id": cp.checkpoint_id,
                "type": cp.type,
                "created_at": cp.created_at.isoformat(),
                "resolved": cp.resolved_at is not None
            }
            for cp in pending_checkpoints
        ],
        "agent_created_at": agent.created_at.isoformat(),
        "agent_updated_at": agent.updated_at.isoformat()
    }
    
    return debug_info

@app.post("/debug/fix-stuck-campaign/{job_id}")
async def fix_stuck_campaign(job_id: str):
    """Try to fix a stuck campaign"""
    agent = agent_manager.get_agent(job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # If agent is stuck in planning, try to create the initial checkpoint
    if agent.status == "planning":
        try:
            # Use default companies for the sector
            companies = SECTOR_COMPANIES.get(agent.sector, [])[:3]
            
            # Create companies with risk assessment
            companies_with_risk = []
            for company in companies:
                risk_info = get_company_risk_info(company)
                companies_with_risk.append({
                    "name": company,
                    "risk_level": risk_info["risk"],
                    "risk_reason": risk_info["reason"]
                })
            
            # Create plan data
            plan_data = {
                "sector": agent.sector,
                "companies": companies,
                "companies_with_risk": companies_with_risk,
                "recipient_email": agent.recipient_email,
                "total_steps": 3,
                "current_step": 1
            }
            
            # Create checkpoint manually
            checkpoint = checkpoint_manager.create_checkpoint(
                job_id, 
                "plan_approval", 
                plan_data, 
                f"Review campaign plan for {agent.sector} sector with {len(companies)} companies"
            )
            
            # Update agent status
            agent.status = "waiting_approval"
            agent.current_step = "planning"
            agent.save()
            
            return {
                "message": "Campaign unstuck successfully",
                "checkpoint_id": checkpoint.checkpoint_id,
                "companies_found": len(companies),
                "new_status": agent.status
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fix campaign: {str(e)}")
    
    else:
        return {
            "message": f"Campaign is not stuck (status: {agent.status})",
            "current_status": agent.status
        }

@app.post("/debug/restart-campaign/{job_id}")
async def restart_campaign(job_id: str):
    """Restart a campaign from scratch"""
    agent = agent_manager.get_agent(job_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        # Store original campaign details
        original_sector = agent.sector
        original_email = agent.recipient_email
        original_autonomy = agent.autonomy_level
        
        # Mark old campaign as failed
        agent.status = "failed"
        agent.save()
        
        # Create new campaign
        new_job_id = str(uuid.uuid4())
        new_agent = agent_manager.create_agent(new_job_id)
        
        # Start the campaign again
        asyncio.create_task(run_enhanced_campaign(
            sector=original_sector,
            job_id=new_job_id,
            recipient_email=original_email,
            autonomy_level=original_autonomy
        ))
        
        return {
            "message": "Campaign restarted successfully",
            "old_job_id": job_id,
            "new_job_id": new_job_id,
            "sector": original_sector
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart campaign: {str(e)}")

@app.get("/debug/all-campaigns")
async def debug_all_campaigns():
    """Get debug info for all campaigns"""
    all_agents = agent_manager.get_all_agents()
    
    campaign_info = []
    for agent in all_agents:
        pending_checkpoints = checkpoint_manager.get_pending_checkpoints(agent.job_id)
        
        campaign_info.append({
            "job_id": agent.job_id,
            "sector": agent.sector,
            "status": agent.status,
            "current_step": agent.current_step,
            "progress": agent.progress,
            "pending_checkpoints": len(pending_checkpoints),
            "created_at": agent.created_at.isoformat(),
            "autonomy_level": agent.autonomy_level
        })
    
    return {
        "total_campaigns": len(all_agents),
        "campaigns": campaign_info
    }