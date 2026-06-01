# Order API

## Endpoints

- `GET /api/orders` - List all orders
- `GET /api/orders/{orderId}` - Get a specific order

## Data Types

- `total_amount` is returned as a decimal-precise string (per OpenAPI spec)
- All monetary values should maintain cent-level precision

## See Also

- [OpenAPI Specification](openapi.yaml)
