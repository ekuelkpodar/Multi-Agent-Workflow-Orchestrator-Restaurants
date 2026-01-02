"""Support Agent - Handles customer complaints, refunds, and escalations."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from src.agents.base import BaseAgent
from src.state.conversation import ConversationManager
from src.state.manager import get_state_manager
from src.utils.prompts import PromptTemplates


class SupportAgent(BaseAgent):
    """
    Support agent that handles customer issues and resolutions.

    Responsibilities:
    - Handle complaints and issues
    - Process refund requests
    - Apply compensation policies
    - Escalate complex cases
    - Access order history for context
    """

    def __init__(self, conversation_manager: ConversationManager):
        super().__init__("support_agent", conversation_manager)
        self.register_tools()

        # Policy thresholds
        self.auto_refund_threshold = Decimal("100.00")
        self.escalation_threshold = 3

    @property
    def system_prompt(self) -> str:
        """Return the support agent system prompt."""
        return PromptTemplates.SUPPORT_AGENT_SYSTEM

    def register_tools(self) -> None:
        """Register support agent tools."""
        self.register_tool("get_order_details", self.get_order_details)
        self.register_tool("issue_refund", self.issue_refund)
        self.register_tool("apply_credit", self.apply_credit)
        self.register_tool("create_ticket", self.create_ticket)
        self.register_tool("escalate_to_human", self.escalate_to_human)
        self.register_tool("get_customer_history", self.get_customer_history)
        self.register_tool("apply_resolution_policy", self.apply_resolution_policy)

    async def get_order_details(self, order_id: UUID) -> dict[str, Any]:
        """
        Get complete order details with timeline.

        Args:
            order_id: Order identifier

        Returns:
            Order details with full history
        """
        state_manager = await get_state_manager()

        # Get order from kitchen system
        kitchen_data = await state_manager.get(f"kitchen:order:{order_id}")

        # Get delivery data
        delivery_data = await state_manager.get(f"delivery:{order_id}")

        if not kitchen_data and not delivery_data:
            return {"error": "Order not found"}

        # Compile order timeline
        timeline = []

        if kitchen_data:
            timeline.append(
                {
                    "stage": "kitchen",
                    "status": kitchen_data.get("status"),
                    "received_at": kitchen_data.get("received_at"),
                    "estimated_ready": kitchen_data.get("estimated_ready"),
                    "actual_ready": kitchen_data.get("actual_ready"),
                }
            )

        if delivery_data:
            timeline.append(
                {
                    "stage": "delivery",
                    "status": delivery_data.get("status"),
                    "driver_name": delivery_data.get("driver_name"),
                    "assigned_at": delivery_data.get("assigned_at"),
                    "estimated_delivery_at": delivery_data.get("estimated_delivery_at"),
                    "delivered_at": delivery_data.get("delivered_at"),
                }
            )

        return {
            "order_id": str(order_id),
            "timeline": timeline,
            "kitchen_details": kitchen_data,
            "delivery_details": delivery_data,
        }

    async def issue_refund(
        self,
        order_id: UUID,
        amount: Decimal,
        reason: str,
        customer_id: UUID,
    ) -> dict[str, Any]:
        """
        Issue a refund for an order.

        Args:
            order_id: Order to refund
            amount: Refund amount
            reason: Refund reason
            customer_id: Customer receiving refund

        Returns:
            Refund details
        """
        # Check if requires approval
        requires_approval = amount > self.auto_refund_threshold

        if requires_approval:
            # Create escalation ticket
            escalation = await self.escalate_to_human(
                order_id=order_id,
                reason=f"Refund approval needed: ${amount} - {reason}",
                context={"amount": float(amount), "reason": reason},
            )

            return {
                "success": False,
                "requires_approval": True,
                "escalation_id": escalation["escalation_id"],
                "message": "Refund requires manager approval. You'll be contacted shortly.",
            }

        # Process refund
        refund_id = uuid4()

        refund_data = {
            "refund_id": str(refund_id),
            "order_id": str(order_id),
            "customer_id": str(customer_id),
            "amount": float(amount),
            "reason": reason,
            "issued_at": datetime.utcnow().isoformat(),
            "status": "processed",
        }

        state_manager = await get_state_manager()
        await state_manager.set(
            f"refund:{refund_id}",
            refund_data,
            ttl=2592000,  # 30 days
        )

        return {
            "success": True,
            "refund_id": str(refund_id),
            "amount": float(amount),
            "message": f"Refund of ${amount} processed successfully.",
        }

    async def apply_credit(
        self,
        customer_id: UUID,
        amount: Decimal,
        reason: str,
    ) -> dict[str, Any]:
        """
        Apply account credit to a customer.

        Args:
            customer_id: Customer to credit
            amount: Credit amount
            reason: Reason for credit

        Returns:
            Credit details
        """
        credit_id = uuid4()

        credit_data = {
            "credit_id": str(credit_id),
            "customer_id": str(customer_id),
            "amount": float(amount),
            "reason": reason,
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(days=90)
            ).isoformat(),  # 90 day expiry
            "status": "active",
        }

        state_manager = await get_state_manager()
        await state_manager.set(
            f"credit:{credit_id}",
            credit_data,
            ttl=7776000,  # 90 days
        )

        # Update customer credit balance
        customer_key = f"customer:{customer_id}"
        customer_data = await state_manager.get(customer_key)

        if customer_data:
            current_balance = Decimal(str(customer_data.get("credit_balance", 0)))
            customer_data["credit_balance"] = float(current_balance + amount)
            await state_manager.set(customer_key, customer_data)

        return {
            "success": True,
            "credit_id": str(credit_id),
            "amount": float(amount),
            "message": f"${amount} credit applied to your account.",
        }

    async def create_ticket(
        self,
        order_id: UUID,
        category: str,
        details: str,
        customer_id: UUID,
    ) -> dict[str, Any]:
        """
        Create a support ticket.

        Args:
            order_id: Related order
            category: Issue category
            details: Issue details
            customer_id: Customer who reported

        Returns:
            Ticket details
        """
        ticket_id = uuid4()

        ticket_data = {
            "ticket_id": str(ticket_id),
            "order_id": str(order_id),
            "customer_id": str(customer_id),
            "category": category,
            "details": details,
            "created_at": datetime.utcnow().isoformat(),
            "status": "open",
            "priority": "normal",
        }

        state_manager = await get_state_manager()
        await state_manager.set(
            f"ticket:{ticket_id}",
            ticket_data,
            ttl=2592000,  # 30 days
        )

        return {
            "ticket_id": str(ticket_id),
            "status": "open",
            "message": "Support ticket created. We'll look into this.",
        }

    async def escalate_to_human(
        self,
        order_id: UUID,
        reason: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Escalate an issue to human support.

        Args:
            order_id: Related order
            reason: Escalation reason
            context: Additional context

        Returns:
            Escalation details
        """
        escalation_id = uuid4()

        escalation_data = {
            "escalation_id": str(escalation_id),
            "order_id": str(order_id),
            "reason": reason,
            "context": context,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending_review",
            "assigned_to": None,
        }

        state_manager = await get_state_manager()
        await state_manager.set(
            f"escalation:{escalation_id}",
            escalation_data,
            ttl=604800,  # 7 days
        )

        return {
            "escalation_id": str(escalation_id),
            "message": "Your issue has been escalated to our management team.",
        }

    async def get_customer_history(self, customer_id: UUID) -> dict[str, Any]:
        """
        Get customer order history and stats.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer history summary
        """
        state_manager = await get_state_manager()
        customer_key = f"customer:{customer_id}"

        customer_data = await state_manager.get(customer_key)

        if not customer_data:
            return {
                "customer_id": str(customer_id),
                "total_orders": 0,
                "message": "No order history found",
            }

        # In production, query database for actual history
        # For demo, return simplified data
        return {
            "customer_id": str(customer_id),
            "total_orders": customer_data.get("total_orders", 0),
            "credit_balance": customer_data.get("credit_balance", 0),
            "is_vip": customer_data.get("is_vip", False),
        }

    async def apply_resolution_policy(
        self,
        issue_category: str,
        order_id: UUID,
        customer_id: UUID,
        order_total: Decimal,
        delay_minutes: int | None = None,
    ) -> dict[str, Any]:
        """
        Apply automated resolution policy based on issue type.

        Args:
            issue_category: Type of issue
            order_id: Related order
            customer_id: Customer ID
            order_total: Order total amount
            delay_minutes: Delivery delay in minutes (for late delivery)

        Returns:
            Resolution details
        """
        resolutions = []

        if issue_category == "late_delivery":
            if delay_minutes is None:
                delay_minutes = 0

            if delay_minutes < 15:
                # 10% off next order
                credit_amount = Decimal("5.00")
                credit_result = await self.apply_credit(
                    customer_id,
                    credit_amount,
                    f"Apology for {delay_minutes} min delay",
                )
                resolutions.append(credit_result)

            elif 15 <= delay_minutes <= 30:
                # 25% refund
                refund_amount = order_total * Decimal("0.25")
                refund_result = await self.issue_refund(
                    order_id,
                    refund_amount,
                    f"25% refund for {delay_minutes} min delay",
                    customer_id,
                )
                resolutions.append(refund_result)

            else:  # > 30 min late
                # Full refund
                refund_result = await self.issue_refund(
                    order_id,
                    order_total,
                    f"Full refund for {delay_minutes} min delay",
                    customer_id,
                )
                resolutions.append(refund_result)

        elif issue_category in ["wrong_item", "missing_item"]:
            # Refund item + 15% credit
            refund_amount = order_total * Decimal("0.30")  # Approximate item cost
            refund_result = await self.issue_refund(
                order_id,
                refund_amount,
                f"Refund for {issue_category}",
                customer_id,
            )

            credit_amount = order_total * Decimal("0.15")
            credit_result = await self.apply_credit(
                customer_id,
                credit_amount,
                "Inconvenience credit",
            )

            resolutions.append(refund_result)
            resolutions.append(credit_result)

        elif issue_category == "quality_issue":
            # Partial or full refund based on severity
            refund_amount = order_total * Decimal("0.50")
            refund_result = await self.issue_refund(
                order_id,
                refund_amount,
                "Quality issue refund",
                customer_id,
            )
            resolutions.append(refund_result)

        else:
            # Create ticket for manual review
            ticket_result = await self.create_ticket(
                order_id,
                issue_category,
                "Customer reported issue",
                customer_id,
            )
            resolutions.append(ticket_result)

        return {
            "issue_category": issue_category,
            "resolutions": resolutions,
            "message": "We've applied the appropriate resolution. Is there anything else we can help with?",
        }


# Import timedelta
from datetime import timedelta
