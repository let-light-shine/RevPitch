# database.py
import sqlite3
import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

class DatabaseManager:
    def __init__(self, db_path: str = "revreach_agents.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Agents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_step TEXT,
                progress INTEGER DEFAULT 0,
                sector TEXT,
                autonomy_level TEXT,
                recipient_email TEXT,
                selected_companies TEXT,  -- JSON array
                contexts TEXT,           -- JSON array
                generated_emails TEXT,   -- JSON object
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # Checkpoints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                job_id TEXT,
                type TEXT NOT NULL,
                message TEXT,
                data TEXT,              -- JSON object
                risk_level TEXT DEFAULT 'medium',
                requires_approval BOOLEAN DEFAULT 1,
                created_at TEXT,
                resolved_at TEXT,
                human_decision TEXT,
                FOREIGN KEY (job_id) REFERENCES agents (job_id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_checkpoints_job_id ON checkpoints(job_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_checkpoints_resolved ON checkpoints(resolved_at)')
        
        conn.commit()
        conn.close()
        
        logging.info("Database initialized successfully")

db_manager = DatabaseManager()

class PersistentAgent:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "planning"
        self.current_step = "initializing"
        self.progress = 0
        self.sector = None
        self.autonomy_level = "supervised"
        self.recipient_email = None
        self.selected_companies = []
        self.contexts = []
        self.generated_emails = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Save to database
        self.save()
    
    def save(self):
        """Save agent to database"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO agents (
                job_id, status, current_step, progress, sector, autonomy_level,
                recipient_email, selected_companies, contexts, generated_emails,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.job_id,
            self.status,
            self.current_step,
            self.progress,
            self.sector,
            self.autonomy_level,
            self.recipient_email,
            json.dumps(self.selected_companies),
            json.dumps(self.contexts),
            json.dumps(self.generated_emails),
            self.created_at.isoformat(),
            self.updated_at.isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def update_progress(self):
        """Update progress based on current step"""
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
        self.updated_at = datetime.now()
        self.save()
    
    @classmethod
    def load(cls, job_id: str):
        """Load agent from database"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM agents WHERE job_id = ?', (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        agent = cls.__new__(cls)
        agent.job_id = row[0]
        agent.status = row[1]
        agent.current_step = row[2]
        agent.progress = row[3]
        agent.sector = row[4]
        agent.autonomy_level = row[5]
        agent.recipient_email = row[6]
        agent.selected_companies = json.loads(row[7] or '[]')
        agent.contexts = json.loads(row[8] or '[]')
        agent.generated_emails = json.loads(row[9] or '{}')
        agent.created_at = datetime.fromisoformat(row[10])
        agent.updated_at = datetime.fromisoformat(row[11])
        
        return agent

class PersistentCheckpoint:
    def __init__(self, checkpoint_id: str, job_id: str, checkpoint_type: str, data: Dict, message: str):
        self.checkpoint_id = checkpoint_id
        self.job_id = job_id
        self.type = checkpoint_type
        self.data = data
        self.message = message
        self.risk_level = "medium"
        self.requires_approval = True
        self.created_at = datetime.now()
        self.resolved_at = None
        self.human_decision = None
        
        # Save to database
        self.save()
    
    def save(self):
        """Save checkpoint to database"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO checkpoints (
                checkpoint_id, job_id, type, message, data, risk_level,
                requires_approval, created_at, resolved_at, human_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.checkpoint_id,
            self.job_id,
            self.type,
            self.message,
            json.dumps(self.data),
            self.risk_level,
            self.requires_approval,
            self.created_at.isoformat(),
            self.resolved_at.isoformat() if self.resolved_at else None,
            self.human_decision
        ))
        
        conn.commit()
        conn.close()
    
    def resolve(self, decision: str):
        """Resolve checkpoint with human decision"""
        self.resolved_at = datetime.now()
        self.human_decision = decision
        self.save()
    
    @classmethod
    def load(cls, checkpoint_id: str):
        """Load checkpoint from database"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM checkpoints WHERE checkpoint_id = ?', (checkpoint_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        checkpoint = cls.__new__(cls)
        checkpoint.checkpoint_id = row[0]
        checkpoint.job_id = row[1]
        checkpoint.type = row[2]
        checkpoint.message = row[3]
        checkpoint.data = json.loads(row[4] or '{}')
        checkpoint.risk_level = row[5]
        checkpoint.requires_approval = bool(row[6])
        checkpoint.created_at = datetime.fromisoformat(row[7])
        checkpoint.resolved_at = datetime.fromisoformat(row[8]) if row[8] else None
        checkpoint.human_decision = row[9]
        
        return checkpoint

class PersistentAgentManager:
    def create_agent(self, job_id: str):
        """Create new agent"""
        agent = PersistentAgent(job_id)
        logging.info(f"Created agent {job_id}")
        return agent
    
    def get_agent(self, job_id: str):
        """Get agent by job_id"""
        return PersistentAgent.load(job_id)
    
    def list_active_agents(self):
        """List all active agents"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT job_id FROM agents 
            WHERE status NOT IN ('completed', 'failed')
            ORDER BY created_at DESC
        ''')
        
        job_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        agents = []
        for job_id in job_ids:
            agent = self.get_agent(job_id)
            if agent:
                agents.append(agent)
        
        return agents
    
    def get_all_agents(self):
        """Get all agents"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT job_id FROM agents ORDER BY created_at DESC')
        job_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        agents = []
        for job_id in job_ids:
            agent = self.get_agent(job_id)
            if agent:
                agents.append(agent)
        
        return agents

class PersistentCheckpointManager:
    def __init__(self):
        self.checkpoint_counter = self._get_checkpoint_counter()
    
    def _get_checkpoint_counter(self):
        """Get current checkpoint counter from database"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM checkpoints')
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def create_checkpoint(self, job_id: str, checkpoint_type: str, data: Dict, message: str):
        """Create new checkpoint"""
        self.checkpoint_counter += 1
        checkpoint_id = f"checkpoint_{self.checkpoint_counter}"
        
        checkpoint = PersistentCheckpoint(checkpoint_id, job_id, checkpoint_type, data, message)
        
        # Update agent status based on autonomy level
        agent = PersistentAgent.load(job_id)
        if agent and agent.autonomy_level == "supervised":
            print(f"🔍 [DEBUG] Setting agent {job_id} to waiting_approval")
            agent.status = "waiting_approval"
            agent.save()
            print(f"✅ [DEBUG] Agent {job_id} status updated to: {agent.status}")
        elif agent and agent.autonomy_level == "automatic":
            # NEW: Auto-approval logic for automatic mode
            print(f"🤖 [AUTO] Auto-approving checkpoint {checkpoint_id} for automatic agent {job_id}")
            agent.status = "executing"
            agent.save()
            
            # Create auto-approval task
            asyncio.create_task(self.auto_approve_checkpoint(checkpoint_id, agent, checkpoint_type, data))
        
        logging.info(f"Created checkpoint {checkpoint_id} for agent {job_id}")
        return checkpoint
    
    async def auto_approve_checkpoint(self, checkpoint_id: str, agent, checkpoint_type: str, data: Dict):
        """Auto-approve checkpoint for automatic mode"""
        try:
            print(f"🤖 [AUTO] Processing auto-approval for {checkpoint_type}")
            
            if checkpoint_type == "plan_approval":
                companies = data.get('companies', [])
                agent.selected_companies = companies
                agent.status = "executing"
                agent.current_step = "fetching_contexts"
                agent.update_progress()
                
                self.resolve_checkpoint(checkpoint_id, "approve", "Auto-approved all companies")
                print(f"🤖 [AUTO] Plan approved, generating emails for {len(companies)} companies")
                
                # Start email generation
                await self.auto_generate_emails_for_agent(agent)
                
            elif checkpoint_type == "email_preview":
                emails = data.get('emails', {})
                agent.selected_emails = list(emails.keys())
                agent.status = "executing"
                agent.current_step = "requesting_send_approval"
                agent.update_progress()
                
                self.resolve_checkpoint(checkpoint_id, "approve", "Auto-approved all emails")
                print(f"🤖 [AUTO] Emails approved, creating send checkpoint")
                
                # Create send checkpoint
                await self.auto_create_send_checkpoint(agent, emails)
                
            elif checkpoint_type == "bulk_send_approval":
                self.resolve_checkpoint(checkpoint_id, "approve", "Auto-approved send")
                print(f"🤖 [AUTO] Send approved, sending emails")
                
                # Send emails
                await self.auto_send_emails_and_complete(agent, data)
                
        except Exception as e:
            print(f"❌ [AUTO] Auto-approval failed: {e}")
            agent.status = "failed"
            agent.save()
            logging.error(f"Auto-approval failed: {e}")
    
    async def auto_generate_emails_for_agent(self, agent):
        """Generate emails for automatic mode"""
        try:
            # Import required functions
            from main import fetch_context_for_company, email_prompt, retry_llm_invoke_with_timeout
            
            agent.current_step = "generating_emails"
            agent.update_progress()
            
            indices = ["devrev-knowledge-hub"]
            emails = {}
            
            for company in agent.selected_companies:
                try:
                    print(f"🤖 [AUTO] Generating email for {company}")
                    context = await fetch_context_for_company(company, indices)
                    prompt = email_prompt.format(**context)
                    email_content = await retry_llm_invoke_with_timeout(prompt)
                    emails[company] = email_content
                except Exception as e:
                    print(f"❌ [AUTO] Email generation failed for {company}: {e}")
                    # Fallback email
                    emails[company] = f"""Dear {company} Leadership Team,

I hope this message finds you well. I'm reaching out from DevRev to discuss how we can help {company} enhance customer engagement and product development processes.

DevRev offers an integrated platform that connects customer feedback directly to engineering teams, enabling faster product iterations and better customer satisfaction.

Would you be open to a brief conversation about how DevRev can support {company}'s growth objectives?

Best regards,
John Doe
DevRev Sales Team"""
            
            agent.generated_emails = emails
            agent.save()
            
            # Create email preview checkpoint
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
            print(f"❌ [AUTO] Email generation failed: {e}")
            agent.status = "failed"
            agent.save()
    
    async def auto_create_send_checkpoint(self, agent, emails):
        """Create send checkpoint for automatic mode"""
        try:
            send_data = {
                "emails": emails,
                "total_steps": 3,
                "current_step": 3,
                "sector": agent.sector,
                "recipient_email": agent.recipient_email
            }
            
            self.create_checkpoint(agent.job_id, "bulk_send_approval", send_data,
                                 f"Auto-sending {len(emails)} emails to {agent.sector} companies")
                                 
        except Exception as e:
            print(f"❌ [AUTO] Send checkpoint creation failed: {e}")
            agent.status = "failed"
            agent.save()
    
    async def auto_send_emails_and_complete(self, agent, data):
        """Send emails and complete campaign for automatic mode"""
        try:
            # Import required functions
            from main import send_email, extract_subject_and_body, email_db
            import re
            
            emails = data.get('emails', {})
            recipient_email = data.get('recipient_email') or agent.recipient_email
            
            agent.current_step = "sending_emails"
            agent.update_progress()
            
            results = []
            for company, raw_body in emails.items():
                subject_extracted, email_body = extract_subject_and_body(raw_body)
                subject = subject_extracted or f"DevRev Partnership Opportunity for {company}"
                
                # Clean placeholders
                placeholder_patterns = [
                    r"(?i)\[.*leadership.*team.*\]",
                    r"(?i)\[.*team.*\]",
                    r"(?i)hi \[.*\]",
                    r"(?i)dear \[.*\]",
                ]
                
                email_lines = email_body.strip().splitlines()
                cleaned_lines = []
                for line in email_lines:
                    line_clean = line.strip()
                    if any(re.search(pat, line_clean) for pat in placeholder_patterns):
                        continue
                    cleaned_lines.append(line)
                cleaned_body = "\n".join(cleaned_lines).strip()
                
                # Add signature if needed
                has_signature = any(sig in email_body.lower() for sig in [
                    "best regards", "sincerely", "devrev sales team", "john doe"
                ])
                
                if not has_signature:
                    signature = "\n\nBest regards,\nJohn Doe\nDevRev Sales Team"
                    full_body = cleaned_body + signature
                else:
                    full_body = cleaned_body
                
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
                    
                    print(f"✅ [AUTO] Email sent to {company}")
                    
                except Exception as e:
                    error_msg = f"failed: {str(e)}"
                    results.append({"company": company, "to": recipient_email, "status": error_msg})
                    print(f"❌ [AUTO] Failed to send to {company}: {str(e)}")
            
            agent.status = "completed"
            agent.current_step = "completed"
            agent.progress = 100
            agent.save()
            
            sent = sum(1 for r in results if r["status"] == "sent")
            print(f"🎉 [AUTO] Campaign completed! Sent = {sent}, Failed = {len(results) - sent}")
            
        except Exception as e:
            print(f"❌ [AUTO] Email sending failed: {e}")
            agent.status = "failed"
            agent.save()
    
    def get_checkpoint(self, checkpoint_id: str):
        """Get checkpoint by ID"""
        return PersistentCheckpoint.load(checkpoint_id)
    
    def get_pending_checkpoints(self, job_id: str):
        """Get pending checkpoints for agent"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT checkpoint_id FROM checkpoints 
            WHERE job_id = ? AND resolved_at IS NULL
            ORDER BY created_at ASC
        ''', (job_id,))
        
        checkpoint_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        checkpoints = []
        for checkpoint_id in checkpoint_ids:
            checkpoint = self.get_checkpoint(checkpoint_id)
            if checkpoint:
                checkpoints.append(checkpoint)
        
        return checkpoints
    
    def resolve_checkpoint(self, checkpoint_id: str, decision: str, feedback: str = None):
        """Resolve checkpoint with human decision"""
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return False
        
        checkpoint.resolve(decision)
        
        # Update agent status
        agent = PersistentAgent.load(checkpoint.job_id)
        if agent:
            # Check if there are more pending checkpoints
            pending = self.get_pending_checkpoints(checkpoint.job_id)
            if not pending:
                agent.status = "executing"
                agent.save()
        
        logging.info(f"Resolved checkpoint {checkpoint_id} with decision: {decision}")
        return True
    
    def get_all_pending_checkpoints(self):
        """Get all pending checkpoints across all agents"""
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT checkpoint_id FROM checkpoints 
            WHERE resolved_at IS NULL
            ORDER BY created_at ASC
        ''')
        
        checkpoint_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        checkpoints = []
        for checkpoint_id in checkpoint_ids:
            checkpoint = self.get_checkpoint(checkpoint_id)
            if checkpoint:
                checkpoints.append(checkpoint)
        
        return checkpoints

# Create persistent managers
persistent_agent_manager = PersistentAgentManager()
persistent_checkpoint_manager = PersistentCheckpointManager()