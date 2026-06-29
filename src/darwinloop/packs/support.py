"""darwinloop packs/support.py — Benchmark pack for customer support agents."""

from __future__ import annotations

from darwinloop._models import BenchmarkTask
from darwinloop.packs.base import BenchmarkPack


class SupportPack(BenchmarkPack):
    """Benchmark pack for customer support intent classification agents.

    Tests intent detection, escalation logic, tone consistency, and FAQ routing.
    """

    @property
    def tasks(self) -> list[BenchmarkTask]:
        return [
            BenchmarkTask(
                id="support_billing",
                name="billing_intent",
                description="Billing question should route to billing_support",
                input="I was charged twice for my subscription this month",
                expected="billing",
            ),
            BenchmarkTask(
                id="support_technical",
                name="technical_intent",
                description="Technical issue should route to technical_support",
                input="The app keeps crashing when I open it",
                expected="technical",
            ),
            BenchmarkTask(
                id="support_escalation",
                name="escalation_detection",
                description="Angry/urgent message should trigger escalation flag",
                input="This is absolutely unacceptable! I want to speak to a manager RIGHT NOW",
                expected="escalat",
            ),
            BenchmarkTask(
                id="support_cancellation",
                name="cancellation_intent",
                description="'I want to cancel' should route to cancellation",
                input="I want to cancel my subscription",
                expected="cancel",
            ),
            BenchmarkTask(
                id="support_faq",
                name="faq_routing",
                description="Simple FAQ question should route to faq",
                input="What are your opening hours?",
                expected="faq",
                must_not_contain="escalat",
            ),
        ]
