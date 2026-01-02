# Multi-Agent Restaurant Orchestrator - Architecture

## System Overview

This system implements a production-grade multi-agent AI architecture for managing restaurant operations. Six specialized agents collaborate to handle the complete order lifecycle from placement to delivery.

## Agent Architecture

### 1. Orchestrator Agent
**Role**: Traffic controller and intent classifier

**Responsibilities**:
- Analyze incoming messages and classify intent
- Route requests to appropriate specialist agents
- Manage conversation state and context
- Handle agent handoffs with full context preservation

**Tools**:
- `classify_intent`: NLP-based intent classification
- `get_menu_info`: General menu information
- `get_hours`: Operating hours

### 2. Order Agent
**Role**: Order processing specialist

**Responsibilities**:
- Parse natural language orders
- Validate item availability with Inventory Agent
- Handle customizations and special requests
- Calculate totals with tax and fees
- Create and confirm orders

**Tools**:
- `get_menu`: Retrieve menu items
- `parse_order_items`: Natural language to structured order
- `calculate_total`: Price calculation with tax
- `create_order`: Order persistence
- `validate_promo_code`: Promotional code validation

### 3. Inventory Agent
**Role**: Stock management specialist

**Responsibilities**:
- Real-time inventory tracking
- Temporary reservations for pending orders
- Intelligent substitution suggestions
- Low stock alerts

**Tools**:
- `check_availability`: Real-time stock check
- `reserve_inventory`: Reserve with TTL
- `release_reservation`: Cancel reservation
- `get_substitutions`: Find alternatives
- `update_stock`: Inventory adjustments

**Data Model**:
```
inventory:{item_id} -> {
    quantity: int,
    low_stock_threshold: int,
    ingredients: list,
    ...
}

reservation:{reservation_id} -> {
    item_id: str,
    quantity: int,
    order_id: UUID,
    expires_at: datetime
}
```

### 4. Kitchen Agent
**Role**: Food preparation coordinator

**Responsibilities**:
- Queue management and prioritization
- Prep time estimation (base time + modifiers)
- Order status tracking (received → preparing → ready)
- Realistic timing simulation

**Tools**:
- `add_to_queue`: Queue order with priority
- `get_queue_status`: Current queue depth
- `update_order_status`: Status transitions
- `get_order_eta`: Time remaining
- `prioritize_order`: VIP/urgent handling
- `estimate_prep_time`: Dynamic calculation

**Prep Time Calculation**:
```
base_time = category_base_time * quantity
modifiers:
  - queue_depth: +2 min per order ahead
  - peak_hours: 1.3x multiplier
  - customizations: +3 min
  - large_orders: +5 min (> 5 items)
```

### 5. Delivery Agent
**Role**: Driver assignment and delivery tracking

**Responsibilities**:
- Driver assignment based on distance and rating
- Delivery time estimation
- Real-time tracking simulation
- Delivery issue reporting

**Tools**:
- `get_available_drivers`: Find nearby drivers
- `assign_driver`: Auto or manual assignment
- `update_driver_status`: Status and location updates
- `get_delivery_eta`: Time to delivery
- `report_delivery_issue`: Issue ticket creation

**Assignment Algorithm**:
```
1. Get available drivers
2. Calculate distance from kitchen
3. Filter by rating (> 4.0)
4. Select closest qualified driver
5. Estimate ETA: distance_km * 3 + 5 (pickup buffer)
```

### 6. Support Agent
**Role**: Issue resolution specialist

**Responsibilities**:
- Complaint handling
- Refund processing (with approval thresholds)
- Credit application
- Policy enforcement
- Escalation management

**Tools**:
- `get_order_details`: Full order history
- `issue_refund`: Refund processing
- `apply_credit`: Account credits
- `create_ticket`: Support ticketing
- `escalate_to_human`: Manager escalation
- `apply_resolution_policy`: Automated resolution

**Resolution Policies**:
```
Late Delivery:
  < 15 min: 10% off next order
  15-30 min: 25% refund
  > 30 min: Full refund

Wrong/Missing Items:
  - Refund item cost
  - 15% credit for inconvenience

Quality Issues:
  - 50% refund (adjustable)
```

## State Management

### Redis Schema

**Conversations**:
```
conversation:{conversation_id} -> ConversationState
  - messages: list[Message]
  - current_agent: str
  - context: dict
  - handoff_history: list[HandoffResult]
```

**Kitchen Queue**:
```
kitchen:queue -> sorted set (score = priority_timestamp)
kitchen:order:{order_id} -> order details with status
```

**Delivery**:
```
delivery:{order_id} -> delivery tracking info
driver:{driver_id} -> driver status and location
```

**Inventory**:
```
inventory:{item_id} -> stock levels
reservation:{reservation_id} -> temp reservations (with TTL)
```

## Communication Flow

### Typical Order Flow

```
1. Customer → Orchestrator
   "I want 2 pepperoni pizzas"

2. Orchestrator classifies intent → "new_order"
   Hands off to Order Agent

3. Order Agent parses items
   Checks with Inventory Agent for availability

4. Inventory Agent confirms stock
   Creates reservation (5 min TTL)

5. Order Agent calculates total
   Confirms with customer

6. Order Agent creates order
   Hands off to Kitchen Agent

7. Kitchen Agent adds to queue
   Estimates prep time (15 min base + queue)
   Starts background prep simulation

8. Kitchen Agent marks ready
   Hands off to Delivery Agent

9. Delivery Agent assigns driver
   Driver picks up and delivers

10. System updates customer via WebSocket
```

### Handoff Protocol

When Agent A hands off to Agent B:

```python
1. Agent A summarizes current state
2. Extracts key entities (order details, customer info)
3. Creates HandoffResult with context
4. Updates conversation state (current_agent = B)
5. Logs handoff with timestamp and reason
6. Agent B receives full context to continue
```

## API Endpoints

### REST API

- `POST /api/v1/conversations` - Start conversation
- `POST /api/v1/conversations/{id}/messages` - Send message
- `GET /api/v1/conversations/{id}` - Get conversation status
- `DELETE /api/v1/conversations/{id}` - End conversation
- `GET /api/v1/orders/{id}` - Get order details
- `GET /api/v1/orders/{id}/tracking` - Track order
- `GET /api/v1/admin/agents/status` - Health check
- `GET /api/v1/admin/metrics` - System metrics
- `POST /api/v1/admin/inventory/update` - Update inventory

### WebSocket

- `WS /ws/{conversation_id}` - Real-time bidirectional communication

**Message Types**:
```json
{
  "type": "message|typing|handoff|error",
  "agent_id": "string",
  "content": "string",
  "metadata": {}
}
```

## Observability

### Structured Logging

Every log entry includes:
```json
{
  "timestamp": "ISO 8601",
  "level": "INFO|WARN|ERROR",
  "agent_id": "string",
  "conversation_id": "UUID",
  "action": "string",
  "duration_ms": 123,
  "tokens": 456
}
```

### Agent Tracing

Full request journey tracking:
```
1. API request received
2. Orchestrator classification (X ms, Y tokens)
3. Handoff to Order Agent
4. Tool: check_availability (Z ms)
5. LLM call (W ms, T tokens)
6. Response to user
```

### Metrics

- `requests_per_agent`: Counter
- `agent_response_time`: Histogram
- `handoffs_per_conversation`: Histogram
- `llm_tokens_used`: Counter by agent
- `tool_calls_per_request`: Counter
- `error_rate_by_agent`: Counter

## Error Handling

### Retry Logic

LLM calls use exponential backoff:
```
Attempt 1: immediate
Attempt 2: wait 1s
Attempt 3: wait 2s
Max attempts: 3
```

### Graceful Degradation

- If agent fails, return to orchestrator
- If inventory check fails, allow order with warning
- If driver assignment fails, provide wait time estimate
- All failures logged for analysis

### Idempotency

- Order creation: Check for duplicate order_id
- Inventory reservation: Use unique reservation_id
- Refunds: Check for existing refund_id

## Scaling Considerations

**Horizontal Scaling**:
- Stateless agents (state in Redis)
- Multiple API instances behind load balancer
- Redis cluster for distributed state

**Performance**:
- Async/await throughout
- Connection pooling for Redis and PostgreSQL
- Tool call caching where appropriate
- Context window management

**High Availability**:
- Redis persistence (AOF + RDB)
- PostgreSQL replication
- Health checks on all services
- Circuit breakers for external dependencies
