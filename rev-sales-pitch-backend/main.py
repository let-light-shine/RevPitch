import os
import uuid
import time
import ast
import asyncio
import logging
import httpx
import pandas as pd
import datetime
from typing import List, Dict
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from slugify import slugify

# 🟢 Load env first
load_dotenv()

# ✅ Validate required env variables
required_envs = [
    "OPENAI_API_KEY", "ES_USERNAME", "ES_PASSWORD",
    "FROM_EMAIL", "MY_EMAIL", "EMAIL_PASSWORD",
    "PERPLEXITY_API_KEY"
]
for var in required_envs:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing environment variable: {var}")

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ OpenAI SDK (new style, used only if not via LangChain)
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ LangChain: new imports (clean, updated)
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import ElasticsearchStore
from langchain.prompts import PromptTemplate

# ✅ Local util for sending emails
from email_utils import send_email, send_summary_email

from pydantic import BaseModel
class CampaignRequest(BaseModel):
    sector: str


# ✅ LangChain LLM and embeddings setup (used across campaign)
llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.2,
    api_key=os.getenv("OPENAI_API_KEY")
)

embedding_model = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ FastAPI App instance
app = FastAPI()

# App state
app.state.batches = {}

# ─── LLM and Elasticsearch Setup ───────────────────────────────────
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.getenv("OPENAI_API_KEY"))
embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

# ─── Prompt Templates ──────────────────────────────────────────────
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
summary_prompt = PromptTemplate.from_template("""
You just ran a cold-email campaign of {total} messages:
– Sent: {sent}
– Failed: {failed}
– Success Rate: {rate:.1f}%

Write a concise 4-sentence executive summary of these results and next steps.
""")

# ─── Request Models ────────────────────────────────────────────────
class SectorInput(BaseModel):
    sector: str

class CompaniesRequest(BaseModel):
    sector: str

class CompanyInput(BaseModel):
    companies: List[str]

class ContextItem(BaseModel):
    company: str
    external_ctx: str
    devrev_ctx: str

class GenerateEmailsRequest(BaseModel):
    contexts: List[ContextItem]

class SendCampaignRequest(BaseModel):
    batch_id: str
    assigned: Dict[str, str]

# Track job state (in-memory for MVP)
job_status = {
    "status": "idle",        # idle | running | completed | failed
    "progress": 0,           # 0 to 100 percent
    "message": "",
    "job_id": None
}

# ─── Helper Functions ──────────────────────────────────────────────
async def get_company_context_from_perplexity_async(company: str) -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a sales intelligence assistant."},
            {"role": "user", "content": f"Summarize the latest strategic, operational, or product challenges faced by {company} in 2024 in exactly 2 sentences. Avoid generic statements. Use citations if possible."}
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



@app.post("/start-campaign")
async def start_campaign(request: Request, payload: CampaignRequest):
    job_id = str(uuid.uuid4())
    app.state.current_job_id = job_id
    app.state.batches[job_id] = {
        "status": "running",
        "step": "starting",
        "output": {},
    }

    asyncio.create_task(run_actual_campaign(payload.sector, job_id))
    return {"message": f"Campaign for {payload.sector} started.", "job_id": job_id}




#async def run_campaign_job(job_id: str, sector: str):
#    result = await run_campaign(SectorInput(sector=sector))
#    app.state.batches[job_id] = result
    
# ─── Campaign Route ────────────────────────────────────────────────
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


async def run_actual_campaign(sector: str, job_id: str):
    output = {
        "step": "init",
        "status": "running",
        "timestamp": str(datetime.datetime.now()),
        "error": None,
        "companies": [],
        "contexts": [],
        "emails": {},
        "assignments": {},
        "results": [],
        "metrics": {},
        "summary": ""
    }

    try:
        print("🚀 [START] Running campaign...")
        logging.info("🔍 Discovering companies...")
        output["step"] = "discovering_companies"

        resp = await retry_llm_invoke(discover_prompt.format(sector=sector))
        raw = resp.content.strip()

        try:
            companies = json.loads(raw)
        except json.JSONDecodeError:
            try:
                companies = ast.literal_eval(raw)
            except Exception as e:
                logging.error(f"Failed to parse company list from LLM. Raw:\n{raw}")
                raise ValueError("❌ LLM response not in list format. Update prompt or parser.") from e

        if isinstance(companies[0], dict) and "name" in companies[0]:
            companies = [c["name"] for c in companies]

        companies = companies[:2]  # ✅ TEMP: Limit to 2 companies
        output["companies"] = companies
        print(f"✅ Companies discovered: {companies}")

        output["step"] = "fetching_contexts"
        logging.info("📚 Fetching contexts...")
        print("⏳ Fetching contexts from Perplexity and Elasticsearch...")

        indices = ["devrev-knowledge-hub", "devrev_yt_100", "devrev_docs_casestudies"]
        semaphore = asyncio.Semaphore(1)

        async def throttled_context_fetch(company):
            async with semaphore:
                return await fetch_context_for_company(company, indices)

        context_tasks = [throttled_context_fetch(c) for c in companies]
        contexts = await asyncio.gather(*context_tasks)
        output["contexts"] = contexts
        print("✅ Contexts fetched")

        output["step"] = "generating_emails"
        logging.info("✍️ Generating emails...")
        print("⏳ Generating personalized emails...")

        emails = {}
        for ctx in contexts:
            prompt = email_prompt.format(**ctx)
            resp = await retry_llm_invoke(prompt)
            emails[ctx["company"]] = resp.content
        output["emails"] = emails
        print("✅ Emails generated")

        output["step"] = "assigning_emails"
        logging.info("📧 Assigning recipient email addresses...")
        assignments = {
            company: "krithikavjk@gmail.com"
            for company in companies
        }
        output["assignments"] = assignments
        print("📧 Test Mode: All emails are being sent to krithikavjk@gmail.com")

        output["step"] = "sending_emails"
        logging.info("📨 Sending emails...")
        print("⏳ Sending emails...")

        results = []
        for company, body in emails.items():
            to_email = assignments[company]
            subject = f"Opportunities for {company} with DevRev"
            try:
                send_email(to_email=to_email, subject=subject, body=body)  # 🔁 Enable this when live
                print(f"✅ (MOCKED) Email sent to {company} ({to_email})")
                results.append({"company": company, "to": to_email, "status": "sent"})
            except Exception as e:
                error_msg = f"❌ Failed to send to {company} ({to_email}): {str(e)}"
                logging.warning(error_msg)
                results.append({"company": company, "to": to_email, "status": f"failed: {str(e)}"})
                print(error_msg)

        output["results"] = results
        sent = sum(1 for r in results if r["status"] == "sent")
        failed = len(results) - sent
        output["metrics"] = {"total": len(results), "sent": sent, "failed": failed}

        logging.info(f"📊 Email Results: Sent = {sent}, Failed = {failed}")
        print(f"📊 Email Results: Sent = {sent}, Failed = {failed}")

        await asyncio.sleep(5)
        summary = (await retry_llm_invoke(
            summary_prompt.format(
                total=len(results), sent=sent, failed=failed,
                rate=(sent / len(results)) * 100 if results else 0
            ))
        ).content
        output["summary"] = summary

        output["status"] = "complete"
        output["step"] = None
        print("✅ Campaign completed successfully")

    except Exception as e:
        output["status"] = "failed"
        output["error"] = str(e)
        output["step"] = "error"
        logging.exception("❌ Campaign failed with error")
        print(f"❌ Campaign failed: {str(e)}")

    # ✅ Store the output in app state for the given job
    app.state.batches[job_id] = {
        "status": output["status"],
        "step": output["step"],
        "output": output
    }
    return output




@app.get("/campaign-status")
def campaign_status():
    job_id = getattr(app.state, "current_job_id", None)
    if not job_id or job_id not in app.state.batches:
        return {
            "status": "idle",
            "progress": 0,
            "message": "",
            "job_id": None,
            "step": None,
            "output": {
                "results": [],
                "companies": [],
                "contexts": [],
                "emails": {},
                "assignments": {},
                "metrics": {},
                "summary": "",
                "error": None
            }
        }

    batch = app.state.batches[job_id]
    return {
        "status": batch["status"],
        "progress": 100 if batch["status"] == "complete" else 0,
        "message": f"Campaign for {job_id} {'completed' if batch['status'] == 'complete' else 'in progress'}.",
        "job_id": job_id,
        "step": batch.get("step", ""),
        "output": batch.get("output", {
            "results": [],
            "companies": [],
            "contexts": [],
            "emails": {},
            "assignments": {},
            "metrics": {},
            "summary": "",
            "error": None
        })
    }





@app.post("/reset-campaign")
async def reset_campaign():
    job_status.update({
        "status": "idle",
        "progress": 0,
        "message": "",
        "job_id": None
    })
    return {"message": "Campaign state reset."}



# ─── Health Check ──────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "running"}


@app.post("/test-email")
def test_email_send():
    from email_utils import send_email
    try:
        send_email(
            to_email="your@email.com",  
            subject="Test Email from FastAPI",
            body="This is a test email sent from the /test-email endpoint."
        )
        return {"status": "success", "message": "Email sent successfully."}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/health")
def health():
    try:
        models = client.models.list()
        return {"status": "ok", "models": [m.id for m in models.data[:2]]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
