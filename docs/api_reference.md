## API Reference

Complete API documentation for the Multi-Agent Restaurant Orchestrator.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication required (add JWT in production).

---

## Conversations

### Create Conversation

Start a new conversation with the system.

**Endpoint**: `POST /api/v1/conversations`

**Request Body** (optional):
```json
{
  "customer_id": "uuid" // optional
}
```

**Response**: `201 Created`
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Conversation started. How can I help you today?"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json"
```

---

### Send Message

Send a message in an existing conversation.

**Endpoint**: `POST /api/v1/conversations/{conversation_id}/messages`

**Request Body**:
```json
{
  "message": "I want to order 2 large pepperoni pizzas"
}
```

**Response**: `200 OK`
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "order_agent",
  "message": "Great! I can help you with that. 2 large pepperoni pizzas...",
  "metadata": {
    "tokens_used": 234,
    "execution_time_ms": 1250.5
  }
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/conversations/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to order pizza"}'
```

---

### Get Conversation Status

Get the current status of a conversation.

**Endpoint**: `GET /api/v1/conversations/{conversation_id}`

**Response**: `200 OK`
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "123e4567-e89b-12d3-a456-426614174000",
  "current_agent": "order_agent",
  "is_active": true,
  "message_count": 8
}
```

---

### End Conversation

Mark a conversation as ended.

**Endpoint**: `DELETE /api/v1/conversations/{conversation_id}`

**Response**: `204 No Content`

---

## Orders

### Get Order Details

Retrieve complete order information.

**Endpoint**: `GET /api/v1/orders/{order_id}`

**Response**: `200 OK`
```json
{
  "order_id": "660e8400-e29b-41d4-a716-446655440000",
  "timeline": [
    {
      "stage": "kitchen",
      "status": "ready",
      "received_at": "2024-01-15T10:30:00Z",
      "estimated_ready": "2024-01-15T10:45:00Z",
      "actual_ready": "2024-01-15T10:43:00Z"
    },
    {
      "stage": "delivery",
      "status": "delivering",
      "driver_name": "John Smith",
      "assigned_at": "2024-01-15T10:43:30Z",
      "estimated_delivery_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

---

### Track Order

Get real-time tracking information.

**Endpoint**: `GET /api/v1/orders/{order_id}/tracking`

**Response**: `200 OK`
```json
{
  "order_id": "660e8400-e29b-41d4-a716-446655440000",
  "kitchen_status": {
    "status": "ready",
    "message": "Your order is ready for pickup!"
  },
  "delivery_status": {
    "status": "delivering",
    "driver_name": "John Smith",
    "estimated_minutes_remaining": 12,
    "estimated_delivery_at": "2024-01-15T11:00:00Z"
  }
}
```

---

## Admin

### Get Agents Status

Health check for all agents.

**Endpoint**: `GET /api/v1/admin/agents/status`

**Response**: `200 OK`
```json
{
  "total_agents": 6,
  "agents": [
    "orchestrator",
    "order_agent",
    "inventory_agent",
    "kitchen_agent",
    "delivery_agent",
    "support_agent"
  ],
  "status": "healthy"
}
```

---

### Get Metrics

Retrieve system metrics.

**Endpoint**: `GET /api/v1/admin/metrics`

**Response**: `200 OK`
```json
{
  "total_conversations": 1523,
  "active_conversations": 45,
  "total_orders": 892,
  "avg_response_time_ms": 1340,
  "agents": {
    "orchestrator": {
      "requests": 1523,
      "avg_tokens": 425
    },
    "order_agent": {
      "requests": 892,
      "avg_tokens": 1150
    }
  }
}
```

---

### Update Inventory

Manually adjust inventory levels.

**Endpoint**: `POST /api/v1/admin/inventory/update`

**Query Parameters**:
- `item_id`: Item identifier (required)
- `quantity`: Quantity value (required)
- `operation`: "set", "add", or "subtract" (default: "set")

**Response**: `200 OK`
```json
{
  "item_id": "pizza_pepperoni",
  "new_quantity": 50
}
```

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/admin/inventory/update?item_id=pizza_pepperoni&quantity=50&operation=set"
```

---

## WebSocket

### Connect to Conversation

Real-time bidirectional communication.

**Endpoint**: `WS /ws/{conversation_id}`

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/550e8400-e29b-41d4-a716-446655440000');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

**Send Message**:
```javascript
ws.send(JSON.stringify({
  type: 'message',
  content: 'I want to order pizza'
}));
```

**Message Types**:

1. **Connected**
```json
{
  "type": "connected",
  "conversation_id": "uuid",
  "message": "Connected! How can I help you today?"
}
```

2. **Message Response**
```json
{
  "type": "message",
  "agent_id": "order_agent",
  "content": "Great! What size pizza would you like?",
  "metadata": {
    "tokens_used": 156,
    "execution_time_ms": 890.3
  }
}
```

3. **Typing Indicator**
```json
{
  "type": "typing",
  "agent_id": "order_agent",
  "content": "typing..."
}
```

4. **Handoff Notification**
```json
{
  "type": "handoff",
  "from_agent": "orchestrator",
  "to_agent": "order_agent",
  "reason": "User intent classified as: new_order"
}
```

5. **Error**
```json
{
  "type": "error",
  "message": "Failed to process message"
}
```

6. **Ping/Pong**
```javascript
// Send
ws.send(JSON.stringify({type: 'ping'}));

// Receive
{
  "type": "pong"
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error description"
}
```

**Common Status Codes**:
- `400` - Bad Request (invalid input)
- `404` - Not Found (conversation/order doesn't exist)
- `500` - Internal Server Error

---

## Rate Limiting

Currently no rate limiting (implement in production).

Recommended limits:
- 100 requests/minute per IP
- 1000 messages/hour per conversation

---

## Sample Workflows

### Complete Order Flow

```bash
# 1. Start conversation
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/conversations \
  | jq -r '.conversation_id')

# 2. Place order
curl -X POST http://localhost:8000/api/v1/conversations/$CONV_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "I want 2 large pepperoni pizzas"}'

# 3. Get status
curl http://localhost:8000/api/v1/conversations/$CONV_ID

# 4. End conversation
curl -X DELETE http://localhost:8000/api/v1/conversations/$CONV_ID
```

### WebSocket Example (JavaScript)

```javascript
const conversationId = '550e8400-e29b-41d4-a716-446655440000';
const ws = new WebSocket(`ws://localhost:8000/ws/${conversationId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'connected':
      console.log('Ready to chat!');
      break;

    case 'message':
      console.log(`${data.agent_id}: ${data.content}`);
      break;

    case 'typing':
      console.log('Agent is typing...');
      break;

    case 'handoff':
      console.log(`Transferred to ${data.to_agent}`);
      break;
  }
};

// Send a message
function sendMessage(text) {
  ws.send(JSON.stringify({
    type: 'message',
    content: text
  }));
}

sendMessage('I want to order pizza');
```
