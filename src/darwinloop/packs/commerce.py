"""darwinloop packs/commerce.py — Benchmark pack for commerce/shopping agents."""

from __future__ import annotations

from darwinloop._models import BenchmarkTask
from darwinloop.packs.base import BenchmarkPack


class CommercePack(BenchmarkPack):
    """Benchmark pack for agents handling commerce/shopping intents.

    Tests product search, cart operations, price extraction, and checkout flow.
    """

    @property
    def tasks(self) -> list[BenchmarkTask]:
        return [
            BenchmarkTask(
                id="commerce_product_search",
                name="product_search",
                description="'Find me a red laptop bag under £50' should route to product_search",
                input="Find me a red laptop bag under £50",
                expected="product_search",
            ),
            BenchmarkTask(
                id="commerce_add_to_cart",
                name="add_to_cart",
                description="'Add the first result to my cart' should route to cart_add",
                input="Add the first result to my cart",
                expected="cart",
            ),
            BenchmarkTask(
                id="commerce_checkout",
                name="checkout_intent",
                description="'I want to buy it' should trigger checkout intent",
                input="I want to buy it now",
                expected="checkout",
            ),
            BenchmarkTask(
                id="commerce_price_query",
                name="price_query",
                description="'How much does it cost?' should trigger price lookup",
                input="How much does it cost?",
                expected="price",
            ),
            BenchmarkTask(
                id="commerce_order_status",
                name="order_status",
                description="'Where is my order?' should route to order_status",
                input="Where is my order? It was placed yesterday.",
                expected="order",
            ),
        ]
