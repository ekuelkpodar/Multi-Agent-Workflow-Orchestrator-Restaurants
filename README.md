# Multi-Agent Workflow Orchestrator for Restaurant Operations

A production-grade multi-agent AI system simulating a ghost kitchen/cloud kitchen operation. Multiple specialized AI agents collaborate to handle customer orders, manage inventory, coordinate delivery, and handle exceptions.

## Overview

This system demonstrates advanced agentic AI architecture with:
- 6 specialized AI agents working in coordination
- Real-time state management with Redis
- Persistent storage with PostgreSQL
- RESTful API and WebSocket support
- Comprehensive observability and tracing
- Production-ready error handling and retries

## Architecture

### Agents
1. **Orchestrator Agent** - Routes requests and manages conversation flow
2. **Order Agent** - Processes customer orders
3. **Inventory Agent** - Manages real-time inventory and substitutions
4. **Kitchen Agent** - Coordinates food preparation and queue management
5. **Delivery Agent** - Assigns drivers and tracks deliveries
6. **Support Agent** - Handles complaints, refunds, and escalations

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Anthropic API key

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd multi-agent-orchestrator
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

3. Start the system:
```bash
docker-compose up -d
```

4. Seed initial data:
```bash
docker-compose exec app python scripts/seed_data.py
```

5. Test the API:
```bash
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json"
```

## Development

### Install dependencies:
```bash
pip install -e .
```

### Run tests:
```bash
pytest tests/ -v --cov=src
```

### Run locally (without Docker):
```bash
# Start Redis and PostgreSQL
docker-compose up -d redis postgres

# Run the API server
uvicorn src.main:app --reload --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Sample Conversation Flow

```python
import requests

# Start conversation
response = requests.post("http://localhost:8000/api/v1/conversations")
conv_id = response.json()["conversation_id"]

# Send message
response = requests.post(
    f"http://localhost:8000/api/v1/conversations/{conv_id}/messages",
    json={"message": "I'd like to order 2 large pepperoni pizzas"}
)

print(response.json()["response"])
```

## Project Structure

```
multi-agent-orchestrator/
├── src/
│   ├── agents/          # All agent implementations
│   ├── api/             # FastAPI routes and websockets
│   ├── models/          # Pydantic data models
│   ├── state/           # State management (Redis)
│   ├── tools/           # Agent tools and utilities
│   └── utils/           # Logging, tracing, prompts
├── tests/               # Comprehensive test suite
├── scripts/             # Utility scripts
└── docs/                # Additional documentation
```

## Features

- **Natural Language Processing**: Agents understand complex, multi-turn conversations
- **Context Preservation**: Seamless handoffs between agents with full context
- **Real-time Updates**: WebSocket support for live order tracking
- **Smart Inventory**: Automatic substitution suggestions for unavailable items
- **Dynamic Routing**: Intelligent driver assignment and ETA calculation
- **Policy Enforcement**: Automated complaint resolution following business rules
- **Observability**: Structured logging with complete agent trace history

## Configuration

Key environment variables in `.env`:

```
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_URL=postgresql://user:pass@postgres:5432/restaurant
REDIS_URL=redis://redis:6379/0
API_PORT=8000
LOG_LEVEL=INFO
```

## License

MIT License

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
