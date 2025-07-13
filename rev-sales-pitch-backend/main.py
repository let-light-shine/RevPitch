from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.elasticsearch import ElasticsearchStore
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from email_utils import send_summary_email  # ⬅️ Import from your email_utils.py
import uuid
import os
import logging

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

# Session memory store
session_memory: Dict[str, List[str]] = {}

# Prompt template
TEMPLATE = """
You are Dev, a friendly and helpful product expert from DevRev. You’re chatting with someone from {company}, who works as a {persona}. Continue the conversation below, using context from DevRev documents.

Conversation history:
{history}

Use only verified facts from the DevRev documents. Answer helpfully, ask relevant follow-up questions, and suggest useful resources or solutions. If they seem very interested, politely offer to schedule a short 20-minute demo call.

Respond:
"""
prompt = PromptTemplate.from_template(TEMPLATE)

# Request model
class ChatRequest(BaseModel):
    session_id: str
    message: str
    company_name: str
    persona: str
    email: str = None  # Optional

# /chat endpoint
@app.post("/chat")
async def chat_with_agent(data: ChatRequest, background_tasks: BackgroundTasks):
    session_id = data.session_id or str(uuid.uuid4())
    session_memory.setdefault(session_id, [])

    logging.info(f"[{session_id}] User: {data.message}")
    session_memory[session_id].append(f"User: {data.message}")

    # Combine search results from both retrievers
    query = f"DevRev helping {data.company_name} - {data.persona} perspective"
    docs = []
    for retriever in retrievers:
        docs.extend(retriever.get_relevant_documents(query))
    context = "\n\n".join(doc.page_content for doc in docs)

    # Generate response
    history = "\n".join(session_memory[session_id])
    prompt_input = prompt.format(company=data.company_name, persona=data.persona, history=history)
    response = llm.invoke(prompt_input)
    session_memory[session_id].append(f"Agent: {response.content}")

    # Trigger email if user is interested
    trigger_phrases = ["schedule a call", "book a demo", "interested", "connect us", "get in touch"]
    if any(phrase in response.content.lower() for phrase in trigger_phrases) and data.email:
        summary_text = f"Session Summary with {data.company_name} ({data.persona}):\n\n" + "\n".join(session_memory[session_id])
        background_tasks.add_task(send_summary_email, data.email, os.environ["FROM_EMAIL"], summary_text)

    return {"session_id": session_id, "response": response.content}

# Optional: trigger summary manually
@app.post("/send-summary")
async def send_summary(session_id: str, to_email: str):
    if session_id not in session_memory:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = "\n".join(session_memory[session_id])
    send_summary_email(to_email, os.environ["FROM_EMAIL"], summary)
    return {"status": "email_sent"}

# Health check
@app.get("/")
def health():
    return {"status": "running"}
