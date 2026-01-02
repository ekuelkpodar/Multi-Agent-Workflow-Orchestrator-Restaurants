"""Workflow state machine for order processing."""

from enum import Enum


class WorkflowState(str, Enum):
    """Workflow states for order processing."""

    INITIAL = "initial"
    TAKING_ORDER = "taking_order"
    CHECKING_INVENTORY = "checking_inventory"
    CONFIRMING_ORDER = "confirming_order"
    ORDER_PLACED = "order_placed"
    KITCHEN_PREPARING = "kitchen_preparing"
    READY_FOR_PICKUP = "ready_for_pickup"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    HANDLING_ISSUE = "handling_issue"
    CANCELLED = "cancelled"


class WorkflowTransitions:
    """Valid workflow state transitions."""

    TRANSITIONS = {
        WorkflowState.INITIAL: [WorkflowState.TAKING_ORDER],
        WorkflowState.TAKING_ORDER: [
            WorkflowState.CHECKING_INVENTORY,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.CHECKING_INVENTORY: [
            WorkflowState.TAKING_ORDER,  # If item unavailable, go back
            WorkflowState.CONFIRMING_ORDER,
        ],
        WorkflowState.CONFIRMING_ORDER: [
            WorkflowState.ORDER_PLACED,
            WorkflowState.TAKING_ORDER,  # Customer wants to change something
            WorkflowState.CANCELLED,
        ],
        WorkflowState.ORDER_PLACED: [
            WorkflowState.KITCHEN_PREPARING,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.KITCHEN_PREPARING: [
            WorkflowState.READY_FOR_PICKUP,
            WorkflowState.HANDLING_ISSUE,
        ],
        WorkflowState.READY_FOR_PICKUP: [
            WorkflowState.OUT_FOR_DELIVERY,
            WorkflowState.HANDLING_ISSUE,
        ],
        WorkflowState.OUT_FOR_DELIVERY: [
            WorkflowState.DELIVERED,
            WorkflowState.HANDLING_ISSUE,
        ],
        WorkflowState.DELIVERED: [WorkflowState.HANDLING_ISSUE],
        WorkflowState.HANDLING_ISSUE: [
            WorkflowState.CANCELLED,
            WorkflowState.DELIVERED,
        ],
    }

    @classmethod
    def can_transition(cls, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        """Check if a state transition is valid."""
        return to_state in cls.TRANSITIONS.get(from_state, [])
