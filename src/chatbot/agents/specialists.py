from __future__ import annotations

import re

from langchain_classic.chains.sql_database.query import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate

from chatbot.config import settings
from chatbot.models import build_chat_model
from chatbot.retrieval.vector_store import PolicyVectorStore


class StructuredDataAgent:
    def __init__(self) -> None:
        self.llm = build_chat_model(temperature=0)
        self.db = SQLDatabase.from_uri(settings.sqlite_uri)
        self.sql_chain = create_sql_query_chain(self.llm, self.db)
        self.summary_prompt = ChatPromptTemplate.from_template(
            """
You are a customer support SQL analyst.
Question: {question}
SQL Query: {sql_query}
SQL Result: {sql_result}

Provide a concise, user-friendly summary for a support executive.
If data is empty, say clearly no matching customer/ticket data was found.
"""
        )

    def answer(self, question: str) -> str:
        sql_query = self._clean_query(self.sql_chain.invoke({"question": question}))
        if not self._is_safe_select_query(sql_query):
            return "Blocked potentially unsafe SQL. Please ask a read-only customer/ticket query."

        sql_result = self.db.run(sql_query)
        msg = self.summary_prompt.format_messages(
            question=question,
            sql_query=sql_query,
            sql_result=sql_result,
        )
        return self.llm.invoke(msg).content

    @staticmethod
    def _clean_query(raw_query: str) -> str:
        query = raw_query.strip()
        query = query.replace("```sql", "").replace("```", "").strip()
        match = re.search(r"SELECT[\s\S]*", query, flags=re.IGNORECASE)
        query = match.group(0).strip() if match else query
        return re.sub(r";\s*$", "", query)

    @staticmethod
    def _is_safe_select_query(sql_query: str) -> bool:
        normalized = " ".join(sql_query.strip().split()).upper()
        if ";" in normalized:
            return False
        if not normalized.startswith("SELECT"):
            return False

        blocked = ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE ", "CREATE ", "ATTACH ")
        return not any(token in normalized for token in blocked)


class PolicyAgent:
    def __init__(self, vector_store: PolicyVectorStore) -> None:
        self.vector_store = vector_store
        self.llm = build_chat_model(temperature=0)
        self.qa_prompt = ChatPromptTemplate.from_template(
            """
You are a policy assistant for customer support.
Question: {question}
Policy Context:
{context}

Answer only using the context above and cite supporting sources inline using tags like [C1], [C2].
If context is insufficient, explicitly say what is missing.
"""
        )

    def answer(self, question: str) -> str:
        context, citations = self.vector_store.search_with_sources(question, k=4)
        messages = self.qa_prompt.format_messages(question=question, context=context)
        answer = self.llm.invoke(messages).content
        if not citations:
            return answer
        return f"{answer}\n\nSources:\n" + "\n".join(citations)
