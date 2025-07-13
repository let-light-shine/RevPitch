from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.elasticsearch import ElasticsearchStore
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from email_utils import send_summary_email
import uuid
import os
import logging

# ————————————————
# Load & validate env vars
# ————————————————
load_dotenv()
required_envs = ["OPENAI_API_KEY", "ES_USERNAME", "ES_PASSWORD", "FROM_EMAIL", "EMAIL_PASSWORD"]
for var in required_envs:
    if not os.environ.get(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

# ————————————————
# Logging & App init
# ————————————————
logging.basicConfig(level=logging.INFO)
app = FastAPI()

# ————————————————
# Elasticsearch + LLM setup
# ————————————————
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"
embedding_model = OpenAIEmbeddings(openai_api_key=os.environ["OPENAI_API_KEY"])
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.environ["OPENAI_API_KEY"])

vectorstore1 = ElasticsearchStore(
    es_url=ES_URL,
    index_name="devrev-knowledge-hub",
    embedding=embedding_model,
    es_user=os.environ["ES_USERNAME"],
    es_password=os.environ["ES_PASSWORD"],
)
vectorstore2 = ElasticsearchStore(
    es_url=ES_URL,
    index_name="devrev_yt_100",
    embedding=embedding_model,
    es_user=os.environ["ES_USERNAME"],
    es_password=os.environ["ES_PASSWORD"],
)
retrievers = [vectorstore1.as_retriever(), vectorstore2.as_retriever()]

# ————————————————
# In-memory session stores
# ————————————————
# session_history holds the back-and-forth transcript
session_history: Dict[str, List[str]] = {}
# session_stage holds current funnel stage: exploring, curious, ready, or disinterested
session_stage: Dict[str, str] = {}

# ————————————————
# RAG Prompt
# ————————————————
CHAT_TEMPLATE = """
You are Dev, a friendly product expert from DevRev. You’re chatting with someone from {company}, who is a {persona}. Their current stage is {stage}. Continue the conversation below, using context from DevRev documents.

Context from knowledge-base:
{context}

Conversation history:
{history}

Answer helpfully, ask good follow-up questions, and only when the user is truly “ready” suggest booking a 20-minute demo call or sending detailed docs.

Respond with just your reply text.
"""
chat_prompt = PromptTemplate.from_template(CHAT_TEMPLATE)

# ————————————————
# Pydantic models
# ————————————————
class ChatRequest(BaseModel):
    session_id: Optional[str]
    message: str
    company_name: str
    persona: str
    email: Optional[str] = None

class StartConversationRequest(BaseModel):
    message: str

# ————————————————
# /start-conversation
# ————————————————
@app.post("/start-conversation")
async def start_conversation(data: StartConversationRequest, background_tasks: BackgroundTasks):
    # 1) spin up a new session_id
    session_id = str(uuid.uuid4())
    # 2) default stage = "curious"
    session_stage[session_id] = "curious"
    # 3) seed the history with the incoming message
    session_history[session_id] = [f"User: {data.message}"]

    logging.info(f"[{session_id}] Started (stage=curious): {data.message}")

    # 4) call into same /chat logic (with empty company/persona placeholders)
    #    in your real flow you'll extract those before start; here we fake to keep loop simple
    chat_req = ChatRequest(
        session_id=session_id,
        message=data.message,
        company_name="Unknown",   # ← replace with real extraction if you have it
        persona="Unknown",
        email=None
    )
    result = await chat_with_agent(chat_req, background_tasks)
    return {
        "session_id": session_id,
        "agent_reply": result["response"],
        "stage": session_stage[session_id],
    }

# ————————————————
# /chat endpoint
# ————————————————
@app.post("/chat")
async def chat_with_agent(data: ChatRequest, background_tasks: BackgroundTasks):
    # session bootstrap
    session_id = data.session_id or str(uuid.uuid4())
    history = session_history.setdefault(session_id, [])
    stage   = session_stage.setdefault(session_id, "curious")

    logging.info(f"[{session_id}][{stage}] User: {data.message}")
    history.append(f"User: {data.message}")

    # 1) gather RAG context
    query = f"DevRev helping {data.company_name} - {data.persona} perspective"
    docs = []
    for r in retrievers:
        docs.extend(r.get_relevant_documents(query))
    context = "\n\n".join(d.page_content for d in docs)

    # 2) build & invoke chat prompt
    prompt_input = chat_prompt.format(
        company=data.company_name,
        persona=data.persona,
        stage=stage,
        context=context,
        history="\n".join(history),
    )
    resp = llm.invoke(prompt_input).content.strip()
    logging.info(f"[{session_id}][{stage}] Agent: {resp}")
    history.append(f"Agent: {resp}")

    # 3) simple stage transition logic
    lower = data.message.lower()
    if any(k in lower for k in ("schedule", "demo", "call", "book")):
        next_stage = "ready"
    elif any(k in lower for k in ("not interested", "no thanks", "nope")):
        next_stage = "disinterested"
    else:
        next_stage = stage  # remain curious or whatever

    session_stage[session_id] = next_stage

    # 4) optionally trigger summary email when they hit “ready”
    if next_stage == "ready" and data.email:
        summary = "\n".join(history)
        background_tasks.add_task(
            send_summary_email,
            data.email,
            os.environ["FROM_EMAIL"],
            f"Conversation summary:\n\n{summary}",
        )

    return {
        "session_id": session_id,
        "response": resp,
        "stage": next_stage,
    }

# ————————————————
# Manual summary
# ————————————————
@app.post("/send-summary")
async def send_summary(session_id: str, to_email: str):
    if session_id not in session_history:
        raise HTTPException(404, "Session not found")
    summary = "\n".join(session_history[session_id])
    send_summary_email(to_email, os.environ["FROM_EMAIL"], summary)
    return {"status": "email_sent"}

@app.get("/")
def health():
    return {"status": "running"}
