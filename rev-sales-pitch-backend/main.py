import os
import random
import uuid
import logging
from typing import List, Dict

import pandas as pd
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from pydantic import BaseModel

from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.elasticsearch import ElasticsearchStore
from dotenv import load_dotenv
import os

from email_utils import send_summary_email, send_email 

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

# ─── Environment & Logging ─────────────────────────────────────────────────────
required_envs = [
    "OPENAI_API_KEY",
    "ES_USERNAME",
    "ES_PASSWORD",
    "FROM_EMAIL",
    "MY_EMAIL",
    "EMAIL_PASSWORD",
]

# ─── Explicitly load the .env file in this same directory ────────────────────
base_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(base_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

# ─── Validate required environment variables ─────────────────────────────────
required_envs = [
    "OPENAI_API_KEY",
    "ES_USERNAME",
    "ES_PASSWORD",
    "FROM_EMAIL",
    "MY_EMAIL",
    "EMAIL_PASSWORD",
]

for var in required_envs:
    if not os.environ.get(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

logging.basicConfig(level=logging.INFO)

# ─── FastAPI App & State ───────────────────────────────────────────────────────
app = FastAPI()

# We'll stash intermediate state on app.state
#   .recipients, .companies, .contexts, .emails, .assignments, .results

# ─── LLM & RAG Setup ───────────────────────────────────────────────────────────
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"

llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.2,
    openai_api_key=os.environ["OPENAI_API_KEY"],
)

embedding_model = OpenAIEmbeddings(openai_api_key=os.environ["OPENAI_API_KEY"])
es_store = ElasticsearchStore(
    es_url=ES_URL,
    index_name="devrev-knowledge-hub",
    embedding=embedding_model,
    es_user=os.environ["ES_USERNAME"],
    es_password=os.environ["ES_PASSWORD"],
)
retriever = es_store.as_retriever()

# ─── Prompt Templates ──────────────────────────────────────────────────────────
discover_prompt = PromptTemplate.from_template(
    "List the top 10 companies in the {sector} sector as a JSON array."
)
external_prompt = PromptTemplate.from_template(
    "Summarize in two sentences the most pressing challenges or recent issues for {company}."
)
email_prompt = PromptTemplate.from_template(
    """
You’re writing a cold email to {company}’s decision-maker.

**External challenges**: {external_ctx}

**DevRev context**: {devrev_ctx}

Write a JSON object with keys "subject" and "body":
{{"subject": "...", "body": "..."}}

Respond *only* in valid JSON.
"""
)
summary_prompt = PromptTemplate.from_template(
    """
You just ran a cold-email campaign of {total} messages:
– Sent: {sent}
– Failed: {failed}
– Success Rate: {rate:.1f}%

Write a concise 4-sentence executive summary of these results and next steps.
"""
)

# ─── Request Models ────────────────────────────────────────────────────────────
class CompaniesRequest(BaseModel):
    sector: str


class ContextRequest(BaseModel):
    companies: List[str]


class EmailsRequest(BaseModel):
    contexts: List[Dict]  # each dict: {company, external_ctx, devrev_ctx}


class AssignRequest(BaseModel):
    # we key off app.state.emails for subject/body
    pass


# ─── 1. Upload Recipients ──────────────────────────────────────────────────────
@app.post("/upload-emails")
async def upload_emails(file: UploadFile = File(...)):
    df = pd.read_excel(file.file)  # or pd.read_csv
    recipients = df["email"].dropna().tolist()
    if not recipients:
        raise HTTPException(400, "No emails found in upload")
    app.state.recipients = recipients
    # clear downstream
    app.state.companies = []
    app.state.contexts = []
    app.state.emails = []
    app.state.assignments = []
    app.state.results = []
    return {"count": len(recipients)}


# ─── 2. Discover Companies ─────────────────────────────────────────────────────
@app.post("/companies")
async def discover_companies(data: CompaniesRequest):
    resp = llm.invoke(discover_prompt.format(sector=data.sector))
    companies = eval(resp.content)
    app.state.companies = companies
    # clear downstream
    app.state.contexts = []
    app.state.emails = []
    app.state.assignments = []
    app.state.results = []
    return {"companies": companies}


# ─── 3. Fetch Contexts ─────────────────────────────────────────────────────────
@app.post("/context")
async def fetch_contexts(data: ContextRequest):
    contexts = []
    for company in data.companies:
        # a) External context via LLM
        ext_resp = llm.invoke(external_prompt.format(company=company))
        external_ctx = ext_resp.content

        # b) DevRev primary context via RAG
        docs = retriever.get_relevant_documents(f"DevRev features for {company}")
        devrev_primary = "\n".join(d.page_content for d in docs)

        # c) DevRev enriched context on that challenge
        docs2 = retriever.get_relevant_documents(f"How DevRev can help with: {external_ctx}")
        devrev_enriched = "\n".join(d.page_content for d in docs2)

        combined = devrev_primary + "\n\n" + devrev_enriched
        contexts.append({
            "company": company,
            "external_ctx": external_ctx,
            "devrev_ctx": combined
        })

    app.state.contexts = contexts
    # clear downstream
    app.state.emails = []
    app.state.assignments = []
    app.state.results = []
    return {"contexts": contexts}


# ─── 4. Generate Emails ────────────────────────────────────────────────────────
# ----------------------------------------------------------------
# cold-email prompt template for /generate-emails
EMAIL_PROMPT = """
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
"""
# ----------------------------------------------------------------

@app.post("/generate-emails")
async def generate_emails(data: GenerateEmailsRequest):
    try:
        emails = {}
        for ctx in data.contexts:
            prompt = EMAIL_PROMPT.format(
                company=ctx.company,
                external_ctx=ctx.external_ctx,
                devrev_ctx=ctx.devrev_ctx,
            )
            resp = llm.invoke(prompt)
            emails[ctx.company] = resp.content
        return {"emails": emails}
    except Exception as e:
        logging.exception("🔥 generate-emails failed")
        raise HTTPException(status_code=400, detail=str(e))


# ─── 5. Assign Recipients ─────────────────────────────────────────────────────
@app.post("/assign-emails")
async def assign_emails(data: AssignEmailsRequest):
    if data.batch_id not in your_internal_store:
        raise HTTPException(404, "batch_id not found")
    # ... your logic ...
    return {"assigned": data.emails}


# ─── 6. Send Campaign ──────────────────────────────────────────────────────────
@app.post("/send-campaign")
async def send_campaign(data: SendCampaignRequest):
    if data.batch_id not in your_internal_store:
        raise HTTPException(404, "batch_id not found")
    # ... dispatch emails ...
    return {"total": X, "sent": Y, "failed": Z, "success_rate": Y/X}


# ─── 7. Metrics ────────────────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    results = getattr(app.state, "results", [])
    total = len(results)
    sent = sum(1 for r in results if r["status"] == "sent")
    failed = total - sent
    rate = (sent / total * 100) if total else 0
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "success_rate": rate
    }


# ─── 8. Campaign Summary ───────────────────────────────────────────────────────
@app.post("/campaign-summary")
async def campaign_summary(background_tasks: BackgroundTasks):
    m = await metrics()
    summary_text = llm.invoke(
        summary_prompt.format(
            total=m["total"],
            sent=m["sent"],
            failed=m["failed"],
            rate=m["success_rate"],
        )
    ).content

    # Email it in background
    background_tasks.add_task(
        send_summary_email,
        to_email=os.environ["MY_EMAIL"],
        from_email=os.environ["FROM_EMAIL"],
        summary=summary_text,
    )

    return {"report": summary_text}


# ─── 9. Health Check ───────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "running"}
