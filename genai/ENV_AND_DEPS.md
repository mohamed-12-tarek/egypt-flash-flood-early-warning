# GenAI: dependencies and .env

## Dependencies (run once from the project root, then commit pyproject.toml + uv.lock)
```powershell
uv add langchain-groq langchain-core
uv add --dev pytest httpx
```
(`chromadb`, `fastapi`, `langchain`, `python-dotenv`, `sqlalchemy`, `pyodbc` are already in pyproject.)

## .env additions
```
GROQ_API_KEY=your_key
GROQ_MODEL_NAME=llama-3.3-70b-versatile
# optional
# CHROMA_DIR=genai/.chroma
# RAG_MAX_DISTANCE=0.75
# CORS_ORIGINS=http://localhost:5173
# GENAI_RATE_LIMIT_RETRIES=4        # retries when Groq answers 429
# GENAI_RATE_LIMIT_MAX_WAIT=30      # never wait longer than this (seconds) inside one request
```
Also add `genai/.chroma/` to `.gitignore`.

## Note on the ODBC line in .env.example
`db_connection.py` reads `SQLSERVER_DRIVER`, but `.env.example` has a line named `ODBC Driver 18 for SQL Server=...`.
Replace it with:  `SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server`
