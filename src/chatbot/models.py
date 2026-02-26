from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from chatbot.config import settings


def build_chat_model(temperature: float = 0):
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )


def build_embeddings():
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )
