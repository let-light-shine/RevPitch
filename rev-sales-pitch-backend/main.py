import os
import asyncio
import logging
import httpx
import pandas as pd
from typing import List, Dict
import datetime
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, APIRouter, Request
from pydantic import BaseModel
from dotenv import load_dotenv, dotenv_values

from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.elasticsearch import ElasticsearchStore
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_utils import send_email, send_summary_email
from slugify import slugify


# ─── Setup ─────────────────────────────────────────────────────────
load_dotenv()
required_envs = [
    "OPENAI_API_KEY", "ES_USERNAME", "ES_PASSWORD",
    "FROM_EMAIL", "MY_EMAIL", "EMAIL_PASSWORD",
    "PERPLEXITY_API_KEY"
]
for var in required_envs:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing environment variable: {var}")
logging.basicConfig(level=logging.INFO)

app = FastAPI()
#router = APIRouter()
#app.include_router(router)  # Ensure router is included

# App state
app.state.batches = {}

# ─── LLM and Elasticsearch Setup ───────────────────────────────────
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.getenv("OPENAI_API_KEY"))
embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

# ─── Prompt Templates ──────────────────────────────────────────────
discover_prompt = PromptTemplate.from_template("List the top 10 companies in the {sector} sector as a JSON array.")
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
async def start_campaign(data: SectorInput, background_tasks: BackgroundTasks):
    job_id = str(uuid4())

    # Update job state
    app.state.batches[job_id] = {
        "status": "running",
        "step": "starting"
    }

    # Add campaign job to background queue
    background_tasks.add_task(run_campaign_job, job_id, data.sector)

    # Return proper JSON response for frontend
    return JSONResponse(
        content={
            "job_id": job_id,
            "status": "started"
        },
        status_code=200
    )

async def run_campaign_job(job_id: str, sector: str):
    result = await run_campaign(SectorInput(sector=sector))
    app.state.batches[job_id] = result
    
# ─── Campaign Route ────────────────────────────────────────────────
async def run_campaign(data: SectorInput):
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

        resp = llm.invoke(discover_prompt.format(sector=data.sector))
        companies = eval(resp.content)
        if isinstance(companies[0], dict) and "name" in companies[0]:
            companies = [c["name"] for c in companies]

        companies = companies[:2]  # ✅ TEMP: Limit to 2 companies
        output["companies"] = companies
        print(f"✅ Companies discovered: {companies}")

        output["step"] = "fetching_contexts"
        logging.info("📚 Fetching contexts...")
        print("⏳ Fetching contexts from Perplexity and Elasticsearch...")

        indices = ["devrev-knowledge-hub", "devrev_yt_100", "devrev_docs_casestudies"]
        context_tasks = [fetch_context_for_company(c, indices) for c in companies]
        contexts = await asyncio.gather(*context_tasks)
        output["contexts"] = contexts
        print("✅ Contexts fetched")

        output["step"] = "generating_emails"
        logging.info("✍️ Generating emails...")
        print("⏳ Generating personalized emails...")

        emails = {}
        for ctx in contexts:
            prompt = email_prompt.format(**ctx)
            resp = llm.invoke(prompt)
            emails[ctx["company"]] = resp.content
        output["emails"] = emails
        print("✅ Emails generated")

        output["step"] = "assigning_emails"
        logging.info("📧 Assigning recipient email addresses...")
        #assignments = {
        #    c: f"{slugify(c)}@licetteam.testinator.com" for c in companies
        #}
        #output["assignments"] = assignments
        #print(f"✅ Emails assigned: {assignments}")
        # Send all emails to Krithika's Gmail for testing
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
                # send_email(to_email=to_email, subject=subject, body=body)  # 🔁 TEMP: Commented for testing
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

        summary = llm.invoke(
            summary_prompt.format(
                total=len(results), sent=sent, failed=failed, rate=(sent / len(results)) * 100 if results else 0
            )
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

    return output



@app.get("/campaign-status/{job_id}")
def get_campaign_status(job_id: str):
    logging.info(f"Checking campaign status for job_id: {job_id}")
    job = app.state.batches.get(job_id)
    if not job:
        logging.warning(f"No job found for job_id: {job_id}")
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return job


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

