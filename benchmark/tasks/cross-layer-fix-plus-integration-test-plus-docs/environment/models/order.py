"""Order ORM model (simulated SQLAlchemy)."""
from decimal import Decimal


class Order:
    """Simulated SQLAlchemy Order model.
    BUG: total_amount uses float (simulating Column(Float)), which loses precision.
    """
    def __init__(self, id, customer, items_count, unit_price, total_amount):
        self.id = id
        self.customer = customer
        self.items_count = items_count
        self.unit_price = unit_price
        # Simulates Column(Float) - loses precision for certain values
        self.total_amount = float(total_amount)

    def to_dict(self):
        return {
            "id": self.id,
            "customer": self.customer,
            "items_count": self.items_count,
            "unit_price": self.unit_price,
            "total_amount": self.total_amount,
        }


# Simulated database
ORDERS = {
    "ORD-1001": Order("ORD-1001", "Alice", 7, 7.141428571428571, 49.99),
    "ORD-1002": Order("ORD-1002", "Bob", 1, 100.00, 100.00),
    "ORD-1003": Order("ORD-1003", "Charlie", 3, 0.10, 0.30),
    "ORD-1004": Order("ORD-1004", "Diana", 10, 9.99, 99.90),
}
