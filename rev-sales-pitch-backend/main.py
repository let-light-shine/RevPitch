import os
import uuid
import asyncio
import logging
import httpx
import pandas as pd
from typing import List, Dict

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

# ─── Load .env and Validate ────────────────────────────────────────
load_dotenv()
required_envs = [
    "OPENAI_API_KEY", "ES_USERNAME", "ES_PASSWORD",
    "FROM_EMAIL", "MY_EMAIL", "EMAIL_PASSWORD",
    "PERPLEXITY_API_KEY"
]
for var in required_envs:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing environment variable: {var}")

# ─── Setup ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
app = FastAPI()
router = APIRouter()
app.include_router(router)

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

class AssignEmailsRequest(BaseModel):
    batch_id: str
    emails: Dict[str, str]

class SendCampaignRequest(BaseModel):
    batch_id: str
    assigned: Dict[str, str]

# ─── Perplexity Async Fetch ────────────────────────────────────────
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

# ─── Multi-Index Retriever ─────────────────────────────────────────
async def multi_index_retriever(company: str, external_ctx: str, indices: list[str]) -> str:
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

# ─── Upload Emails ─────────────────────────────────────────────────
@app.post("/upload-emails")
async def upload_emails(file: UploadFile = File(...)):
    df = pd.read_excel(file.file)
    recipients = df["email"].dropna().tolist()
    if not recipients:
        raise HTTPException(400, "No emails found in upload")
    app.state.recipients = recipients
    app.state.companies = []
    app.state.contexts = []
    app.state.emails = []
    app.state.results = []
    return {"count": len(recipients)}

# ─── Discover Companies ────────────────────────────────────────────
@app.post("/companies")
async def discover_companies(data: CompaniesRequest):
    resp = llm.invoke(discover_prompt.format(sector=data.sector))
    companies = eval(resp.content)
    app.state.companies = companies
    app.state.contexts = []
    app.state.emails = []
    app.state.results = []
    return {"companies": companies}

# ─── Fetch Context ─────────────────────────────────────────────────
@router.post("/context")
async def fetch_contexts(data: CompanyInput):
    indices = ["devrev-knowledge-hub", "devrev_yt_100"]
    tasks = [fetch_context_for_company(company, indices) for company in data.companies]
    contexts = await asyncio.gather(*tasks)

    app.state.contexts = contexts
    app.state.emails = []
    app.state.results = []
    return {"contexts": contexts}

async def fetch_context_for_company(company: str, indices: list[str]):
    logging.info(f"Fetching context for {company}")
    external_ctx = await get_company_context_from_perplexity_async(company)
    try:
        devrev_ctx = await multi_index_retriever(company, external_ctx, indices)
        if not devrev_ctx:
            raise ValueError("No context returned")
    except Exception as e:
        logging.warning(f"RAG failed for {company}: {e}")
        devrev_ctx = (
            "DevRev is a modern CRM and issue-tracking platform that connects customer issues "
            "to engineering workstreams, improving responsiveness, alignment, and productivity."
        )
    return {
        "company": company,
        "external_ctx": external_ctx,
        "devrev_ctx": devrev_ctx,
    }

# ─── Generate Emails ───────────────────────────────────────────────
@app.post("/generate-emails")
async def generate_emails(data: GenerateEmailsRequest):
    try:
        emails = {}
        for ctx in data.contexts:
            prompt = email_prompt.format(
                company=ctx.company,
                external_ctx=ctx.external_ctx.strip(),
                devrev_ctx=ctx.devrev_ctx.strip()
            )
            resp = llm.invoke(prompt)
            emails[ctx.company] = resp.content
        app.state.emails = emails
        return {"emails": emails}
    except Exception as e:
        logging.exception("Failed to generate emails")
        raise HTTPException(status_code=400, detail=str(e))

# ─── Assign Emails ─────────────────────────────────────────────────
@app.post("/assign-emails")
@router.post("/assign-emails")
async def assign_emails(data: CompanyInput, request: Request):
    assignments = {}
    domain = "licetteam.testinator.com"

    for company in data.companies:
        slug = slugify(company)
        email = f"{slug}@{domain}"
        assignments[company] = email

    request.app.state.assignments = assignments
    return {"assignments": assignments}


# ─── Send Campaign ─────────────────────────────────────────────────

config = dotenv_values(".env")

@router.post("/send-campaign")
async def send_campaign(request: Request):
    emails = request.app.state.emails
    assignments = request.app.state.assignments

    results = []

    for entry in emails:
        company = entry["company"]
        to_email = assignments.get(company)
        email_body = entry["email"]

        try:
            msg = MIMEMultipart()
            msg["From"] = config["FROM_EMAIL"]
            msg["To"] = to_email
            msg["Subject"] = f"Solutions for {company}"

            msg.attach(MIMEText(email_body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(config["FROM_EMAIL"], config["EMAIL_PASSWORD"])
                server.sendmail(config["FROM_EMAIL"], to_email, msg.as_string())

            results.append({"company": company, "to": to_email, "status": "sent"})

        except Exception as e:
            results.append({"company": company, "to": to_email, "status": f"failed: {str(e)}"})

    request.app.state.results = results
    return {"results": results}


# ─── Metrics ───────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    results = getattr(app.state, "results", [])
    total = len(results)
    sent = sum(1 for r in results if r["status"] == "sent")
    failed = total - sent
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "success_rate": (sent / total * 100) if total else 0
    }

# ─── Campaign Summary ──────────────────────────────────────────────
@app.post("/campaign-summary")
async def campaign_summary(background_tasks: BackgroundTasks):
    m = await metrics()
    summary = llm.invoke(summary_prompt.format(**m)).content
    background_tasks.add_task(
        send_summary_email,
        to_email=os.getenv("MY_EMAIL"),
        from_email=os.getenv("FROM_EMAIL"),
        summary=summary
    )
    return {"report": summary}

# ─── Health Check ──────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "running"}
