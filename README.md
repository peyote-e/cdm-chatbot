# CDM Banking RAG Chatbot

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

```bash
cp .env.example .env
```

Fill in `.env`:

```bash
VOYAGE_API_KEY=your_voyage_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
NEO4J_PASSWORD=your_neo4j_password_here
```

## Start Docker

```bash
docker compose up --build -d
```

## Run Ingestion

```bash
docker compose exec -T api python scripts/ingest.py
```

## Run API Checks

```bash
curl http://localhost:8000/health
```

```bash
curl -s -X POST http://localhost:8000/query/hybrid \
  -H "Content-Type: application/json" \
  -d '{"question":"What fields does the Bank entity have?"}'
```

```bash
curl -s -X POST http://localhost:8000/query/compare \
  -H "Content-Type: application/json" \
  -d '{"question":"Which entities are related to Account?"}'
```

## Inspect A Chunk

```bash
curl -s -X POST http://localhost:8000/chunk \
  -H "Content-Type: application/json" \
  -d '{"entity_name":"Bank","attribute_detail":"full"}'
```

## Run Tests

```bash
pytest -q
```

or in Docker:

```bash
docker compose exec -T api pytest -q
```

## Restart After Code Changes

```bash
docker compose down && docker compose up --build -d
```

## Fresh Reset And Re-Ingest

```bash
docker compose down -v
docker compose up --build -d
docker compose exec -T api python scripts/ingest.py
```

## Stop Docker

```bash
docker compose down
```
