
"""
VICTOR Memory System
Implements four types of memory:
1. Short-term: Active conversation context
2. Long-term (Semantic): Vector embeddings of facts, documents, conversations
3. Episodic: Specific events and interactions with timestamps
4. Procedural: Learned workflows and user habits
"""
import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import chromadb
from chromadb.config import Settings
import yaml


@dataclass
class MemoryEntry:
    """Single memory unit."""
    id: str
    content: str
    memory_type: str  # 'short_term', 'semantic', 'episodic', 'procedural'
    timestamp: str
    importance: float  # 0.0 to 1.0
    metadata: Dict[str, Any]
    embedding_id: Optional[str] = None


class MemoryManager:
    """
    Unified memory management with multiple storage backends.
    """

    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.data_dir = self.config['system']['data_dir']
        os.makedirs(self.data_dir, exist_ok=True)

        # SQLite for structured memories (episodic, procedural, preferences)
        self.db_path = os.path.join(self.data_dir, "memory.db")
        self._init_sqlite()

        # ChromaDB for semantic/vector memory
        self.vector_path = self.config['memory']['vector_db_path']
        os.makedirs(self.vector_path, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(path=self.vector_path)

        # Collections
        self.facts_collection = self.chroma_client.get_or_create_collection("facts")
        self.conversations_collection = self.chroma_client.get_or_create_collection("conversations")
        self.documents_collection = self.chroma_client.get_or_create_collection("documents")

        # Short-term buffer
        self.short_term: List[Dict[str, Any]] = []
        self.max_short_term = self.config['memory']['max_short_term']

        # User preference cache
        self.preferences: Dict[str, Any] = {}
        self._load_preferences()

    def _init_sqlite(self):
        """Initialize SQLite schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Episodic memory: specific events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id TEXT PRIMARY KEY,
                event TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                context TEXT,
                outcome TEXT,
                importance REAL DEFAULT 0.5,
                tags TEXT
            )
        """)

        # Procedural memory: how to do things (learned workflows)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procedural_memory (
                id TEXT PRIMARY KEY,
                task_pattern TEXT NOT NULL,
                steps TEXT NOT NULL,
                success_rate REAL DEFAULT 1.0,
                last_used TEXT,
                use_count INTEGER DEFAULT 0
            )
        """)

        # Adaptive learning: task performance and improvement history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_learning (
                id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                execution_time REAL,
                success INTEGER,  -- 1 = success, 0 = failure
                user_feedback TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)

        # User preferences and facts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT,
                confidence REAL DEFAULT 1.0,
                last_updated TEXT
            )
        """)

        # Daily summaries for long-term context compression
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_summaries (
                date TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                key_events TEXT,
                topics TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_preferences(self):
        """Load user preferences into memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_preferences")
        for row in cursor.fetchall():
            try:
                self.preferences[row[0]] = json.loads(row[1])
            except:
                self.preferences[row[0]] = row[1]
        conn.close()

    # ==================== SHORT-TERM MEMORY ====================

    def add_to_short_term(self, role: str, content: str, metadata: Dict = None):
        """Add message to short-term conversation buffer."""
        entry = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.short_term.append(entry)

        # Keep only recent messages
        if len(self.short_term) > self.max_short_term:
            # Archive oldest to long-term before removing
            old = self.short_term.pop(0)
            self._archive_message(old)

    def get_short_term_context(self, limit: int = None) -> List[Dict]:
        """Get recent conversation context for LLM prompt."""
        if limit is None:
            limit = self.max_short_term
        return self.short_term[-limit:]

    def clear_short_term(self):
        """Clear short-term buffer (e.g., new session)."""
        for entry in self.short_term:
            self._archive_message(entry)
        self.short_term = []

    def _archive_message(self, entry: Dict):
        """Archive a message to vector DB for long-term retrieval."""
        doc_id = hashlib.md5(
            (entry['content'] + entry['timestamp']).encode()
        ).hexdigest()

        self.conversations_collection.add(
            documents=[entry['content']],
            metadatas=[{
                'role': entry['role'],
                'timestamp': entry['timestamp'],
                **entry.get('metadata', {})
            }],
            ids=[doc_id]
        )

    # ==================== SEMANTIC MEMORY (Vector) ====================

    def store_fact(self, fact: str, category: str = "general", importance: float = 0.5):
        """Store a factual memory with semantic embedding."""
        doc_id = hashlib.md5(fact.encode()).hexdigest()

        self.facts_collection.add(
            documents=[fact],
            metadatas=[{
                'category': category,
                'importance': importance,
                'timestamp': datetime.now().isoformat()
            }],
            ids=[doc_id]
        )

    def recall_facts(self, query: str, n_results: int = 5) -> List[Dict]:
        """Semantically search stored facts."""
        results = self.facts_collection.query(
            query_texts=[query],
            n_results=n_results
        )

        memories = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                memories.append({
                    'content': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else 0
                })
        return memories

    def index_document(self, file_path: str, content: str):
        """Index a document for semantic search."""
        doc_id = hashlib.md5(file_path.encode()).hexdigest()

        self.documents_collection.add(
            documents=[content],
            metadatas=[{
                'source': file_path,
                'indexed_at': datetime.now().isoformat()
            }],
            ids=[doc_id]
        )

    def search_documents(self, query: str, n_results: int = 3) -> List[Dict]:
        """Search indexed documents."""
        results = self.documents_collection.query(
            query_texts=[query],
            n_results=n_results
        )

        docs = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                docs.append({
                    'content': doc[:500] + "..." if len(doc) > 500 else doc,
                    'source': results['metadatas'][0][i].get('source', 'unknown'),
                    'relevance': 1 - (results['distances'][0][i] if results['distances'] else 0)
                })
        return docs

    # ==================== ADAPTIVE LEARNING ====================

    def record_task_performance(self, task_name: str, task_type: str, execution_time=None,
                                 success=True, user_feedback=None, metadata=None):
        """
        Record task performance for adaptive learning and improvement.
        Victor will use this data to get better at tasks over time!
        """
        import hashlib
        task_id = hashlib.md5(
            (task_name + task_type + datetime.now().isoformat()).encode()
        ).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO adaptive_learning 
            (id, task_name, task_type, execution_time, success, user_feedback, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            task_name,
            task_type,
            execution_time,
            1 if success else 0,
            user_feedback,
            datetime.now().isoformat(),
            json.dumps(metadata or {})
        ))
        conn.commit()
        conn.close()

    def get_task_performance_stats(self, task_type=None):
        """Get performance statistics for tasks to drive improvement."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if task_type:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_tasks,
                    AVG(success) as avg_success_rate,
                    AVG(execution_time) as avg_execution_time,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_tasks
                FROM adaptive_learning 
                WHERE task_type = ?
            """, (task_type,))
        else:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_tasks,
                    AVG(success) as avg_success_rate,
                    AVG(execution_time) as avg_execution_time,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_tasks
                FROM adaptive_learning
            """)
        
        row = cursor.fetchone()
        stats = {
            'total_tasks': row[0],
            'avg_success_rate': row[1] if row[1] else 0,
            'avg_execution_time': row[2] if row[2] else 0,
            'successful_tasks': row[3] if row[3] else 0
        }
        
        conn.close()
        return stats

    # ==================== EPISODIC MEMORY ====================

    def record_episode(self, event: str, context: str = "", outcome: str = "", 
                       importance: float = 0.5, tags: List[str] = None):
        """Record a specific event/interaction."""
        episode_id = hashlib.md5(
            (event + datetime.now().isoformat()).encode()
        ).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO episodic_memory 
            (id, event, timestamp, context, outcome, importance, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_id,
            event,
            datetime.now().isoformat(),
            context,
            outcome,
            importance,
            json.dumps(tags or [])
        ))
        conn.commit()
        conn.close()

        # Also store in vector DB for semantic retrieval
        self.store_fact(
            f"Event: {event}. Context: {context}. Outcome: {outcome}",
            category="episodic",
            importance=importance
        )

    def recall_episodes(self, query: str = None, limit: int = 10) -> List[Dict]:
        """Retrieve recent or relevant episodes."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if query:
            # Simple text search in SQLite (could be enhanced with FTS)
            cursor.execute("""
                SELECT * FROM episodic_memory 
                WHERE event LIKE ? OR context LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
        else:
            cursor.execute("""
                SELECT * FROM episodic_memory 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))

        episodes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return episodes

    # ==================== PROCEDURAL MEMORY ====================

    def learn_procedure(self, task_pattern: str, steps: List[str]):
        """Learn a new workflow/procedure."""
        proc_id = hashlib.md5(task_pattern.encode()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO procedural_memory 
            (id, task_pattern, steps, last_used, use_count)
            VALUES (?, ?, ?, ?, COALESCE(
                (SELECT use_count FROM procedural_memory WHERE id = ?), 0
            ) + 1)
        """, (
            proc_id,
            task_pattern,
            json.dumps(steps),
            datetime.now().isoformat(),
            proc_id
        ))
        conn.commit()
        conn.close()

    def recall_procedure(self, task_description: str) -> Optional[List[str]]:
        """Find a learned procedure matching the task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Simple matching (can be enhanced with embeddings)
        cursor.execute("""
            SELECT steps FROM procedural_memory 
            WHERE task_pattern LIKE ?
            ORDER BY use_count DESC, last_used DESC
            LIMIT 1
        """, (f"%{task_description}%",))

        result = cursor.fetchone()
        conn.close()

        if result:
            return json.loads(result[0])
        return None

    def get_all_procedures(self) -> List[Dict]:
        """List all learned procedures."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM procedural_memory ORDER BY use_count DESC")
        procedures = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return procedures

    # ==================== USER PREFERENCES ====================

    def set_preference(self, key: str, value: Any, category: str = "general", confidence: float = 1.0):
        """Store a user preference."""
        self.preferences[key] = value

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_preferences 
            (key, value, category, confidence, last_updated)
            VALUES (?, ?, ?, ?, ?)
        """, (
            key,
            json.dumps(value),
            category,
            confidence,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a user preference."""
        return self.preferences.get(key, default)

    def get_preferences_by_category(self, category: str) -> Dict[str, Any]:
        """Get all preferences in a category."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, value FROM user_preferences WHERE category = ?",
            (category,)
        )
        result = {}
        for row in cursor.fetchall():
            try:
                result[row[0]] = json.loads(row[1])
            except:
                result[row[0]] = row[1]
        conn.close()
        return result

    # ==================== CONTEXT ASSEMBLY ====================

    def build_context_prompt(self, current_query: str) -> str:
        """
        Build a rich context prompt for the LLM including:
        - Relevant facts
        - Recent episodes
        - Applicable procedures
        - User preferences
        """
        context_parts = []

        # 1. Relevant facts about user/query
        relevant_facts = self.recall_facts(current_query, n_results=3)
        if relevant_facts:
            context_parts.append("## Relevant Knowledge:")
            for fact in relevant_facts:
                context_parts.append(f"- {fact['content']}")

        # 2. Recent episodes (last 24 hours)
        recent = self.recall_episodes(limit=5)
        if recent:
            context_parts.append("\n## Recent Activity:")
            for ep in recent[:3]:
                time_str = ep['timestamp'][:16]  # Trim to minutes
                context_parts.append(f"- [{time_str}] {ep['event']}")

        # 3. Applicable procedures
        procedure = self.recall_procedure(current_query)
        if procedure:
            context_parts.append("\n## Known Procedure:")
            for i, step in enumerate(procedure, 1):
                context_parts.append(f"{i}. {step}")

        # 4. Active preferences
        prefs = self.get_preferences_by_category("behavior")
        if prefs:
            context_parts.append("\n## User Preferences:")
            for k, v in prefs.items():
                context_parts.append(f"- {k}: {v}")

        return "\n".join(context_parts) if context_parts else ""

    # ==================== MAINTENANCE ====================

    def summarize_day(self) -> str:
        """Generate end-of-day summary and compress memories."""
        today = datetime.now().strftime("%Y-%m-%d")
        episodes = self.recall_episodes(limit=50)

        if not episodes:
            return "No significant activity today."

        # Simple extraction (in production, use LLM to summarize)
        topics = set()
        key_events = []
        for ep in episodes:
            key_events.append(ep['event'])
            if ep['tags']:
                try:
                    tags = json.loads(ep['tags'])
                    topics.update(tags)
                except:
                    pass

        summary = f"Today: {len(episodes)} interactions. Key: {', '.join(key_events[:5])}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO daily_summaries (date, summary, key_events, topics)
            VALUES (?, ?, ?, ?)
        """, (
            today,
            summary,
            json.dumps(key_events[:10]),
            json.dumps(list(topics))
        ))
        conn.commit()
        conn.close()

        return summary

    def persist(self):
        """Force persistence of all vector stores."""
        pass


