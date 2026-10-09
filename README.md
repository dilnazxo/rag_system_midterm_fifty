# Engineering Manual RAG

The Streamlit app searches the saved FAISS index of engineering manuals. **Retrieval Only** shows the matching excerpts without an OpenAI API key. **RAG Answer** generates an answer and displays its cited manual pages.

## Run locally

From the project root, activate your virtual environment and install the declared dependencies:

```bash
python -m venv .venv
source .venv/Scripts/activate  # Git Bash on Windows
python -m pip install -r requirements.txt
```

The existing `data/index/chunks.faiss` and `data/index/chunks.json` files must be present. The app uses this saved index and will report a missing or stale index rather than rebuilding it.

For RAG Answer, copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `OPENAI_MODEL` there, or provide them as environment variables. Existing environment variables take precedence. Keep `.env` private. Retrieval Only does not need API credentials.

Start the interface from the project root:

```bash
streamlit run app.py
```

Questions are independent; the chat history is displayed in the browser session. The local embedding model must already be cached for offline loading.
