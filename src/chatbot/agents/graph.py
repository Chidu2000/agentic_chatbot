from __future__ import annotations

import re
from typing import Literal, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from chatbot.agents.specialists import PolicyAgent, StructuredDataAgent
from chatbot.models import build_chat_model


Route = Literal["SQL", "POLICY", "BOTH", "NONE"]


class AgentState(TypedDict, total=False):
    question: str
    route: Route
    sql_answer: str
    policy_answer: str
    final_answer: str


class MultiAgentWorkflow:
    def __init__(self, sql_agent: StructuredDataAgent, policy_agent: PolicyAgent) -> None:
        self.sql_agent = sql_agent
        self.policy_agent = policy_agent
        self.router_llm = build_chat_model(temperature=0)
        self.synth_llm = build_chat_model(temperature=0)

        self.router_prompt = ChatPromptTemplate.from_template(
            """
Classify the user question into one label:
- SQL: asks for customer profile, account, ticket history, or structured records.
- POLICY: asks for policy, terms, refund/returns/process from documents.
- BOTH: requires both customer/ticket data and policy context.
- NONE: none of the above.

Return only one label from: SQL, POLICY, BOTH, NONE.
Question: {question}
"""
        )

        self.synthesis_prompt = ChatPromptTemplate.from_template(
            """
You are a customer support copilot.
User Question: {question}

Structured Data Agent Output:
{sql_answer}

Policy Agent Output:
{policy_answer}

Provide a single clear response for John.
Preserve citation tags and source lines exactly as provided (e.g., [C1], Sources: ...).
If one source is unavailable, continue with available source and mention the gap briefly.
"""
        )

        graph = StateGraph(AgentState)
        graph.add_node("router", self.router_node)
        graph.add_node("sql_agent", self.sql_node)
        graph.add_node("policy_agent", self.policy_node)
        graph.add_node("synthesizer", self.synth_node)

        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router",
            self.route_from_state,
            {
                "sql": "sql_agent",
                "policy": "policy_agent",
                "both": "sql_agent",
                "none": "synthesizer",
            },
        )
        graph.add_conditional_edges(
            "sql_agent",
            self.after_sql,
            {
                "to_policy": "policy_agent",
                "to_synth": "synthesizer",
            },
        )
        graph.add_edge("policy_agent", "synthesizer")
        graph.add_edge("synthesizer", END)

        self.app = graph.compile()

    def invoke(self, question: str) -> str:
        result = self.app.invoke({"question": question})
        return result.get("final_answer", "I could not generate a response.")

    def invoke_with_meta(self, question: str) -> dict[str, str]:
        result = self.app.invoke({"question": question})
        return {
            "answer": result.get("final_answer", "I could not generate a response."),
            "route": result.get("route", "NONE"),
        }

    def router_node(self, state: AgentState) -> AgentState:
        messages = self.router_prompt.format_messages(question=state["question"])
        raw = self.router_llm.invoke(messages).content.strip().upper()
        label = re.sub(r"[^A-Z]", "", raw)
        if label not in {"SQL", "POLICY", "BOTH", "NONE"}:
            label = "NONE"
        return {"route": label}

    @staticmethod
    def route_from_state(state: AgentState) -> str:
        route = state.get("route", "NONE")
        if route == "SQL":
            return "sql"
        if route == "POLICY":
            return "policy"
        if route == "BOTH":
            return "both"
        return "none"

    @staticmethod
    def after_sql(state: AgentState) -> str:
        return "to_policy" if state.get("route") == "BOTH" else "to_synth"

    def sql_node(self, state: AgentState) -> AgentState:
        try:
            answer = self.sql_agent.answer(state["question"])
        except Exception as exc:
            answer = f"Structured data retrieval failed: {exc}"
        return {"sql_answer": answer}

    def policy_node(self, state: AgentState) -> AgentState:
        try:
            answer = self.policy_agent.answer(state["question"])
        except Exception as exc:
            answer = f"Policy retrieval failed: {exc}"
        return {"policy_answer": answer}

    def synth_node(self, state: AgentState) -> AgentState:
        route = state.get("route", "NONE")
        sql_answer = state.get("sql_answer", "No structured data output.")
        policy_answer = state.get("policy_answer", "No policy output.")
        if route == "SQL":
            return {"final_answer": sql_answer}
        if route == "POLICY":
            return {"final_answer": policy_answer}
        messages = self.synthesis_prompt.format_messages(
            question=state["question"],
            sql_answer=sql_answer,
            policy_answer=policy_answer,
        )
        final = self.synth_llm.invoke(messages).content
        return {"final_answer": final}
