from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Dict, List
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.elasticsearch import ElasticsearchStore
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from starlette.background import BackgroundTasks
import smtplib
from email.message import EmailMessage
import uuid
import os

# Load environment variables
load_dotenv()

# FastAPI App
app = FastAPI()

# Configs
ES_URL = "https://022f4eb51f6946e7b708ab92c67d59ab.ap-south-1.aws.elastic-cloud.com:443"
embedding_model = OpenAIEmbeddings(openai_api_key=os.environ["OPENAI_API_KEY"])
llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=os.environ["OPENAI_API_KEY"])

# Elasticsearch stores
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

# Session state to simulate memory
session_memory: Dict[str, List[str]] = {}

# Email sender (SMTP-based basic setup)
def send_summary_email(to_email: str, from_email: str, summary: str):
    msg = EmailMessage()
    msg.set_content(summary)
    msg["Subject"] = "DevRev Sales Conversation Summary"
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(from_email, os.environ["EMAIL_PASSWORD"])
        smtp.send_message(msg)

# Prompt template
TEMPLATE = """
You are an expert conversational sales agent for DevRev. Continue the conversation with the potential customer from {company} who is a {persona}. Use the history and context below.

Conversation history:
{history}

Use only verified facts from DevRev sources. Ask follow-up questions, share relevant case studies if needed, and guide them toward booking a 20-minute demo. If they seem very interested, ask them politely if they’d like to schedule the call.

Respond:
"""

prompt = PromptTemplate.from_template(TEMPLATE)

# Request model
class ChatRequest(BaseModel):
    session_id: str
    message: str
    company_name: str
    persona: str
    email: str = None  # Optional for summary

@app.post("/chat")
async def chat_with_agent(data: ChatRequest, background_tasks: BackgroundTasks):
    # Get or create session history
    session_id = data.session_id or str(uuid.uuid4())
    if session_id not in session_memory:
        session_memory[session_id] = []

    # Add user message
    session_memory[session_id].append(f"User: {data.message}")

    # Fetch docs
    query = f"DevRev helping {data.company_name} - {data.persona} perspective"
    context = "\n\n".join([doc.page_content for doc in retrievers[0].get_relevant_documents(query)])

    # Generate response
    history = "\n".join(session_memory[session_id])
    prompt_input = prompt.format(company=data.company_name, persona=data.persona, history=history)
    response = llm.invoke(prompt_input)

    # Store agent reply
    session_memory[session_id].append(f"Agent: {response.content}")

    # Trigger summary email if user shows interest
    if "schedule a call" in response.content.lower() and data.email:
        summary_text = f"Session Summary with {data.company_name} ({data.persona}):\n\n" + "\n".join(session_memory[session_id])
        background_tasks.add_task(send_summary_email, data.email, os.environ["FROM_EMAIL"], summary_text)

    return {"session_id": session_id, "response": response.content}

# Root check
@app.get("/")
def health():
    return {"status": "running"}