"""Minimal Streamlit chat interface for the saved engineering-manual index."""

from pathlib import Path

import streamlit as st
from openai import APIConnectionError, APIStatusError, AuthenticationError

from answer import ABSTENTION, answer_question
from retrieval import ManualIndex, SearchResult


PROJECT_ROOT = Path(__file__).resolve().parent
RETRIEVAL_ONLY = "Retrieval Only"
RAG_ANSWER = "RAG Answer"


@st.cache_resource(show_spinner="Loading saved manual index...")
def get_index() -> ManualIndex:
    """Load the existing FAISS index and local encoder once per Streamlit process."""
    return ManualIndex.load_or_build(
        manuals_dir=PROJECT_ROOT / "data" / "manuals",
        index_dir=PROJECT_ROOT / "data" / "index",
        allow_build=False,
    )


def respond(question: str, mode: str, index: ManualIndex) -> dict:
    """Return one chat reply without making an API call in Retrieval Only mode."""
    if mode == RETRIEVAL_ONLY:
        sources = index.search(question, top_k=5)
        if not sources:
            return {"content": "No matching manual was found in the saved index.", "sources": [], "cited_evidence_ids": [], "status": "warning"}
        return {
            "content": f"Found {len(sources)} relevant excerpts in the saved manuals.",
            "sources": sources,
            "cited_evidence_ids": [],
            "status": "normal",
        }
    if mode != RAG_ANSWER:
        raise ValueError(f"Unknown mode: {mode}")

    result = answer_question(question, manual_index=index)
    if not result["sources"]:
        return {"content": "No matching manual was found in the saved index.", "sources": [], "cited_evidence_ids": [], "status": "warning"}
    if result["answer"] == ABSTENTION:
        return {
            "content": "The retrieved excerpts do not contain enough information to answer. Try a more specific model or parameter.",
            "sources": result["sources"],
            "cited_evidence_ids": [],
            "status": "warning",
        }
    return {
        "content": result["answer"],
        "sources": result["sources"],
        "cited_evidence_ids": result["cited_evidence_ids"],
        "status": "normal",
    }


def render_reply(reply: dict) -> None:
    if reply["status"] == "warning":
        st.warning(reply["content"])
    else:
        st.markdown(reply["content"])

    sources: list[SearchResult] = reply["sources"]
    if reply["cited_evidence_ids"]:
        st.markdown("**Cited sources**")
        for evidence_id in reply["cited_evidence_ids"]:
            source = sources[evidence_id - 1]
            st.write(f"[{evidence_id}] {source['source_file']}, page {source['page']}")

    if sources:
        with st.expander(f"Retrieved evidence ({len(sources)})"):
            for number, source in enumerate(sources, start=1):
                st.markdown(f"**[{number}] {source['source_file']} — page {source['page']}**")
                st.caption(f"Chunk: {source['chunk_id']} · Similarity: {source['score']:.4f}")
                st.write(source["text"])


def main() -> None:
    st.set_page_config(page_title="Engineering Manual RAG", page_icon="📚")
    st.title("Engineering Manual RAG")
    st.caption("Ask questions about the manuals in the saved FAISS index.")
    mode = st.radio("Mode", (RETRIEVAL_ONLY, RAG_ANSWER), horizontal=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                st.caption(message["mode"])
                render_reply(message["reply"])

    question = st.chat_input("Ask about an engineering manual")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    try:
        reply = respond(question, mode, get_index())
    except FileNotFoundError:
        reply = {"content": "The saved FAISS index is missing or stale. Check data/index before starting the app.", "sources": [], "cited_evidence_ids": [], "status": "warning"}
    except AuthenticationError:
        reply = {"content": "The OpenAI API rejected the configured key. Check OPENAI_API_KEY in your environment or project-root .env.", "sources": [], "cited_evidence_ids": [], "status": "warning"}
    except APIConnectionError:
        reply = {"content": "Could not connect to the OpenAI API. Check your network or proxy settings.", "sources": [], "cited_evidence_ids": [], "status": "warning"}
    except APIStatusError as error:
        reply = {"content": f"The OpenAI API returned HTTP {error.status_code}.", "sources": [], "cited_evidence_ids": [], "status": "warning"}
    except RuntimeError as error:
        content = (
            "RAG Answer needs OPENAI_API_KEY and OPENAI_MODEL in the project-root .env or environment. Retrieval Only works without them."
            if "OPENAI_API_KEY and OPENAI_MODEL must be set" in str(error)
            else "The saved index or local embedding model could not be loaded."
        )
        reply = {"content": content, "sources": [], "cited_evidence_ids": [], "status": "warning"}
    except ValueError:
        reply = {"content": "The generated answer could not be validated against the retrieved evidence.", "sources": [], "cited_evidence_ids": [], "status": "warning"}

    st.session_state.messages.append({"role": "assistant", "mode": mode, "reply": reply})
    with st.chat_message("assistant"):
        st.caption(mode)
        render_reply(reply)


if __name__ == "__main__":
    main()
