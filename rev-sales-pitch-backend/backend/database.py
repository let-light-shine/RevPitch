# database.py
import sqlite3
import json
import uuid
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
        
        # Update agent status if supervised
        agent = PersistentAgent.load(job_id)
        if agent and agent.autonomy_level == "supervised":
            agent.status = "waiting_approval"
            agent.save()
        
        logging.info(f"Created checkpoint {checkpoint_id} for agent {job_id}")
        return checkpoint
    
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