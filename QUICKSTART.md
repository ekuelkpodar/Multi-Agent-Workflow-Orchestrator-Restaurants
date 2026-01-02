# Quick Start Guide

Get the Multi-Agent Restaurant Orchestrator running in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ (for local development)
- Anthropic API key ([get one here](https://console.anthropic.com/))

## Option 1: Docker (Recommended)

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Anthropic API key
nano .env  # or use your preferred editor
```

Make sure to set:
```
ANTHROPIC_API_KEY=your_actual_api_key_here
```

### 2. Start the System

```bash
# Start all services (PostgreSQL, Redis, API)
docker-compose up -d

# Watch logs
docker-compose logs -f app
```

Wait for the services to be healthy (about 30 seconds).

### 3. Seed Initial Data

```bash
# Seed menu, inventory, and drivers
docker-compose exec app python scripts/seed_data.py
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Start a conversation
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json"

# You'll get back a conversation_id - use it to send messages
CONV_ID="<paste-conversation-id-here>"

curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to order 2 large pepperoni pizzas"}'
```

### 5. Access API Documentation

Visit http://localhost:8000/docs for interactive API documentation.

---

## Option 2: Local Development

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package in development mode
pip install -e ".[dev]"
```

### 2. Start Infrastructure

```bash
# Start just Redis and PostgreSQL
docker-compose up -d redis postgres
```

### 3. Setup Environment

```bash
cp .env.example .env
# Edit .env with your Anthropic API key and update database URLs:
# DATABASE_URL=postgresql+asyncpg://restaurant_user:restaurant_pass@localhost:5432/restaurant_db
# REDIS_URL=redis://localhost:6379/0
```

### 4. Run the Application

```bash
# Run the FastAPI server
uvicorn src.main:app --reload --port 8000
```

### 5. Seed Data (in another terminal)

```bash
source venv/bin/activate
python scripts/seed_data.py
```

---

## Sample Conversations

### Scenario 1: Simple Order

```bash
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/conversations | jq -r '.conversation_id')

# Place order
curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "I want 2 large pepperoni pizzas and a coke"}' | jq '.message'

# Provide delivery address (if asked)
curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "123 Main St, New York, NY 10001"}' | jq '.message'

# Confirm order
curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "Yes, confirm the order"}' | jq '.message'
```

### Scenario 2: Item Unavailable

```bash
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/conversations | jq -r '.conversation_id')

# Try to order unavailable item (after inventory depleted)
curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "I want buffalo wings"}' | jq '.message'

# System suggests alternatives from same category
```

### Scenario 3: Order Status Check

```bash
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/conversations | jq -r '.conversation_id')

curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "Where is my order #12345?"}' | jq '.message'
```

### Scenario 4: Complaint & Refund

```bash
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/conversations | jq -r '.conversation_id')

curl -X POST "http://localhost:8000/api/v1/conversations/$CONV_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "My pizza arrived cold and 45 minutes late"}' | jq '.message'

# Support agent handles complaint and applies policy
```

---

## Using WebSocket (Real-Time)

### With JavaScript

```javascript
const conversationId = 'new';  // or existing UUID
const ws = new WebSocket(`ws://localhost:8000/ws/${conversationId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.agent_id}]:`, data.content);
};

// Send message
ws.send(JSON.stringify({
  type: 'message',
  content: 'I want to order pizza'
}));
```

### With Python

```python
import asyncio
import websockets
import json

async def chat():
    uri = "ws://localhost:8000/ws/new"
    async with websockets.connect(uri) as websocket:
        # Receive welcome
        message = await websocket.recv()
        print(json.loads(message))

        # Send message
        await websocket.send(json.dumps({
            "type": "message",
            "content": "I want to order 2 pepperoni pizzas"
        }))

        # Receive response
        response = await websocket.recv()
        print(json.loads(response))

asyncio.run(chat())
```

---

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_agents/test_base.py -v
```

### Manual Testing Workflow

1. **Start conversation** → Get conversation_id
2. **Send order message** → Orchestrator routes to Order Agent
3. **Order Agent checks inventory** → Verifies availability
4. **Confirm order** → Order created
5. **Kitchen processes** → Status updates
6. **Driver assigned** → Delivery tracking
7. **Check order status** → Real-time updates

---

## Monitoring

### View Logs

```bash
# Docker
docker-compose logs -f app

# Filter by agent
docker-compose logs -f app | grep "agent_id.*order_agent"

# View structured logs
docker-compose logs app | jq '.'
```

### Check Redis State

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# View all keys
KEYS *

# Get conversation
GET conversation:<uuid>

# Get inventory
GET inventory:pizza_pepperoni

# View kitchen queue
ZRANGE kitchen:queue 0 -1 WITHSCORES
```

### Check PostgreSQL (when implemented)

```bash
docker-compose exec postgres psql -U restaurant_user -d restaurant_db

\dt  # List tables
SELECT * FROM orders;
```

---

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs

# Restart services
docker-compose down
docker-compose up -d
```

### Connection errors

```bash
# Check service health
docker-compose ps

# All services should show (healthy)
```

### Redis connection failed

```bash
# Test Redis
docker-compose exec redis redis-cli ping
# Should return: PONG
```

### API returns 500 errors

```bash
# Check if Anthropic API key is set
docker-compose exec app env | grep ANTHROPIC

# Check logs for detailed error
docker-compose logs app | tail -100
```

### Inventory shows zero

```bash
# Re-seed data
docker-compose exec app python scripts/seed_data.py

# Or reset and re-seed
docker-compose exec app python scripts/reset_state.py
docker-compose exec app python scripts/seed_data.py
```

---

## Stopping the System

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clears all data)
docker-compose down -v
```

---

## Next Steps

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Read Architecture**: See [docs/architecture.md](docs/architecture.md)
3. **API Reference**: See [docs/api_reference.md](docs/api_reference.md)
4. **Customize Agents**: Modify prompts in [src/utils/prompts.py](src/utils/prompts.py)
5. **Add Features**: Extend agents with new tools

---

## Production Checklist

Before deploying to production:

- [ ] Replace hardcoded secrets with proper secret management
- [ ] Enable authentication (JWT tokens)
- [ ] Add rate limiting
- [ ] Set up proper logging aggregation (ELK, Datadog, etc.)
- [ ] Configure CORS appropriately
- [ ] Set up monitoring and alerting
- [ ] Implement database migrations (Alembic)
- [ ] Add comprehensive error handling
- [ ] Load test the system
- [ ] Set up CI/CD pipeline
- [ ] Configure SSL/TLS
- [ ] Add request validation and sanitization
- [ ] Implement proper session management
- [ ] Set up backup and disaster recovery
- [ ] Add security headers
- [ ] Conduct security audit

Enjoy building with the Multi-Agent Restaurant Orchestrator! 🍕🤖
