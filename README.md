# Inventory Management API

FastAPI backend with PostgreSQL, fully containerized with Docker Compose.

## Run

```bash
docker compose up --build
```

API docs are available at:

- http://localhost:4000/docs
- http://localhost:4000/redoc

## Services

- `api`: FastAPI application
- `db`: PostgreSQL 16 database

## Main Endpoints

Products:

- `POST /products`
- `GET /products`
- `GET /products/{id}`
- `PUT /products/{id}`
- `DELETE /products/{id}`

Customers:

- `POST /customers`
- `GET /customers`
- `GET /customers/{id}`
- `DELETE /customers/{id}`

Orders:

- `POST /orders`
- `GET /orders`
- `GET /orders/{id}`
- `DELETE /orders/{id}`

## Example Order Payload

```json
{
  "customer_id": 1,
  "items": [
    {
      "product_id": 1,
      "quantity": 2
    }
  ]
}
```

The backend validates stock availability, reduces inventory, and calculates the total amount automatically.
