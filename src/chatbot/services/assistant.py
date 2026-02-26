from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from chatbot.agents.graph import MultiAgentWorkflow
from chatbot.data.db import get_engine
from chatbot.agents.specialists import PolicyAgent, StructuredDataAgent
from chatbot.data.seed import seed_data
from chatbot.retrieval.vector_store import PolicyVectorStore


class ChatbotService:
    def __init__(self) -> None:
        self.vector_store = PolicyVectorStore()
        self.sql_agent = StructuredDataAgent()
        self.policy_agent = PolicyAgent(self.vector_store)
        self.workflow = MultiAgentWorkflow(self.sql_agent, self.policy_agent)

    def initialize_sql_data(self) -> str:
        seed_data()
        return "Synthetic demo SQL data initialized in the local database."

    def has_sql_data(self) -> bool:
        engine = get_engine()
        with engine.begin() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar_one()
        return int(count) > 0

    def ensure_sql_data(self) -> str:
        if self.has_sql_data():
            return "Existing local SQL demo data detected (auto-seed skipped)."
        return self.initialize_sql_data()

    def ingest_policy_directory(self, directory: str) -> str:
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return "Invalid directory. Provide a valid folder path containing PDF files."

        pdf_paths = [str(p) for p in dir_path.glob("*.pdf")]
        if not pdf_paths:
            return "No PDF files found in the provided directory."

        chunks = self.vector_store.ingest_pdfs(pdf_paths)
        return f"Ingested {len(pdf_paths)} PDF(s) into vector DB with {chunks} text chunk(s)."

    def ask(self, question: str) -> str:
        return self.workflow.invoke(question)

    def ask_with_meta(self, question: str) -> dict[str, str]:
        return self.workflow.invoke_with_meta(question)
