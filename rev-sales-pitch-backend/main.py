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
import json

# Load environment variables
load_dotenv()

# Validate required environment variables
required_envs = ["OPENAI_API_KEY", "ES_USERNAME", "ES_PASSWORD", "FROM_EMAIL", "EMAIL_PASSWORD"]
for var in required_envs:
    if not os.environ.get(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

# Set up logging
logging.basicConfig(level=logging.INFO)

# FastAPI App
app = FastAPI()

# Elasticsearch configuration
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"

# Initialize LangChain components
embedding_model = OpenAIEmbeddings(openai_api_key=os.environ["OPENAI_API_KEY"])
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.environ["OPENAI_API_KEY"])

vectorstore1 = ElasticsearchStore(
    es_url=ES_URL,
    index_name="devrev-knowledge-hub",
    embedding=embedding_model,
    es_user=os.environ["ES_USERNAME"],
    es_password=os.environ["ES_PASSWORD"]
)

vectorstore2 = ElasticsearchStore(
    es_url=ES_URL,
    index_name="devrev_yt_100",
    embedding=embedding_model,
    es_user=os.environ["ES_USERNAME"],
    es_password=os.environ["ES_PASSWORD"]
)

retrievers = [vectorstore1.as_retriever(), vectorstore2.as_retriever()]

# In-memory stores
session_memory: Dict[str, List[str]] = {}
session_stage: Dict[str, str] = {}   # Tracks current stage per session

# Helper: classify user intent stage
def classify_stage(message: str, history: str) -> str:
    prompt = f"""
Based on the conversation history and the user's latest message, classify the user's buyer intent stage as one of:
- exploring
- curious
- ready
- disinterested

Conversation history:
{history}

Latest user message:
\"\"\"{message}\"\"\"

Respond with exactly one of: exploring, curious, ready, disinterested.
"""
    result = llm.invoke(prompt)
    return result.content.strip().lower()

# Helper: build stage-aware prompt
def intelligent_prompt(company: str, persona: str, history: str, context: str, stage: str) -> str:
    follow_up = {
        "exploring": "Ask a clarifying question to understand their needs better.",
        "curious": "Share relevant use cases or examples from DevRev, then gently ask if they’d like more details.",
        "ready": "Offer to schedule a short 20-minute demo call or send detailed documentation.",
        "disinterested": "Thank them politely, offer a fallback resource, and gracefully end the conversation."
    }
    return f"""
You are Dev, a friendly and helpful product expert from DevRev. You're speaking to a {persona} from {company}. Use only verified facts from DevRev documents.

Context from DevRev:
{context}

Conversation history:
{history}

The user is in the **{stage}** stage of their buyer journey. Your instruction:
{follow_up[stage]}

Respond as Dev:
"""

# Prompt template for RAG chat (fallback if needed)
RAG_TEMPLATE = """
You are Dev, a friendly and helpful product expert from DevRev. You’re chatting with someone from {company}, who works as a {persona}. Continue the conversation using context from DevRev documents.

Context:
{context}

Conversation history:
{history}

Respond:
"""
rag_prompt = PromptTemplate.from_template(RAG_TEMPLATE)

# Request models
class ChatRequest(BaseModel):
    session_id: str
    message: str
    company_name: str
    persona: str
    email: Optional[str] = None 

class ExtractInfoRequest(BaseModel):
    message: str

class StartConversationRequest(BaseModel):
    message: str

# Health check
@app.get("/")
def health():
    return {"status": "running"}

# Send summary manually
@app.post("/send-summary")
async def send_summary(session_id: str, to_email: str):
    if session_id not in session_memory:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = "\n".join(session_memory[session_id])
    send_summary_email(to_email, os.environ["FROM_EMAIL"], summary)
    return {"status": "email_sent"}

# Extract structured info from first message
@app.post("/extract-info")
def extract_info(data: ExtractInfoRequest):
    extract_prompt = f"""
You will be given the first message of a conversation with a potential customer.

Extract the following fields:
- company_name
- persona (e.g., Developer, Product Manager)
- interest (what they are trying to solve or explore)
- is_lead: "Yes" or "No"

Respond in valid JSON.

Message:
\"\"\"{data.message}\"\"\"
"""
    result = llm.invoke(extract_prompt)
    return {"extracted": result.content}

# Start conversation: extract info + first agent reply
@app.post("/start-conversation")
async def start_conversation(data: StartConversationRequest, background_tasks: BackgroundTasks):
    # Step 1: extract info
    extract_prompt = f"""
You will be given the first message of a conversation with a potential customer.

Extract the following:
- company_name
- persona
- interest
- is_lead

Respond in JSON.

Message:
\"\"\"{data.message}\"\"\"
"""
    result = llm.invoke(extract_prompt)
    try:
        info = json.loads(result.content)
    except json.JSONDecodeError:
        info = eval(result.content)

    # Initialize session
    session_id = str(uuid.uuid4())
    session_memory[session_id] = [f"User: {data.message}"]
    session_stage[session_id] = "exploring"

    # Step 2: get first agent reply
    chat_data = ChatRequest(
        session_id=session_id,
        message=data.message,
        company_name=info["company_name"],
        persona=info["persona"],
        email=None
    )
    chat_resp = await chat_with_agent(chat_data, background_tasks)
    return {
        "session_id": session_id,
        "agent_reply": chat_resp["response"],
        "extracted": info
    }

# Main chat endpoint with progressive stages
@app.post("/chat")
async def chat_with_agent(data: ChatRequest, background_tasks: BackgroundTasks):
    session_id = data.session_id or str(uuid.uuid4())
    # Ensure memory & stage
    history_list = session_memory.setdefault(session_id, [])
    stage = session_stage.get(session_id, "exploring")

    # Append user message
    logging.info(f"[{session_id}] User: {data.message}")
    history_list.append(f"User: {data.message}")
    history = "\n".join(history_list)

    # Classify new stage
    new_stage = classify_stage(data.message, history)
    if new_stage != stage:
        logging.info(f"[{session_id}] Stage updated: {stage} → {new_stage}")
        stage = session_stage[session_id] = new_stage

    # Handle disinterest
    if stage == "disinterested":
        reply = "I understand—feel free to reach out if you have more questions in the future!"
        history_list.append(f"Agent: {reply}")
        return {"session_id": session_id, "response": reply, "stage": stage}

    # Fetch RAG context
    query = f"DevRev helping {data.company_name} - {data.persona} perspective"
    docs = []
    for retriever in retrievers:
        docs.extend(retriever.get_relevant_documents(query))
    context = "\n\n".join(doc.page_content for doc in docs)

    # Generate stage-aware reply
    prompt_text = intelligent_prompt(
        company=data.company_name,
        persona=data.persona,
        history=history,
        context=context,
        stage=stage
    )
    response = llm.invoke(prompt_text)
    history_list.append(f"Agent: {response.content}")

    # If ready stage and email provided, send summary email
    if stage == "ready" and data.email:
        summary = "\n".join(history_list)
        background_tasks.add_task(
            send_summary_email,
            data.email,
            os.environ["FROM_EMAIL"],
            f"DevRev Chat Summary:\n\n{summary}"
        )

    return {"session_id": session_id, "response": response.content, "stage": stage}
