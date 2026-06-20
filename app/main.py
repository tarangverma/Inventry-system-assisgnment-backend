from decimal import Decimal
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.auth import create_access_token, get_current_user, hash_password, user_to_dict, verify_password
from app.database import Base, engine, get_db


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Inventory Management API", version="1.0.0")

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://inventry-system-assisgnment-fronten.vercel.app",
]
if os.getenv("CORS_ORIGINS"):
    allowed_origins.extend(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def strip_api_prefix(request, call_next):
    if request.scope["path"].startswith("/api/"):
        request.scope["path"] = request.scope["path"][4:]
    elif request.scope["path"] == "/api":
        request.scope["path"] = "/"
    return await call_next(request)


def auth_response(user: models.User):
    return {"data": {"token": create_access_token(user), "user": user_to_dict(user)}}


def ensure_demo_user():
    db = next(get_db())
    try:
        existing_user = db.query(models.User).filter(models.User.email == "admin@inventory.test").first()
        if existing_user is None:
            db.add(
                models.User(
                    name="Admin",
                    email="admin@inventory.test",
                    password_hash=hash_password("Admin@123"),
                )
            )
            db.commit()
    finally:
        db.close()


ensure_demo_user()


def get_product_or_404(db: Session, product_id: int) -> models.Product:
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def get_customer_or_404(db: Session, customer_id: int) -> models.Customer:
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserRegister, db: Session = Depends(get_db)):
    user = models.User(
        name=user_in.name,
        email=user_in.email.lower(),
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User email already exists",
        ) from exc
    db.refresh(user)
    return auth_response(user)


@app.post("/auth/login")
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email.lower()).first()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return auth_response(user)


@app.get("/auth/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"data": {"user": user_to_dict(current_user)}}


@app.post("/products", response_model=schemas.ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(product_in: schemas.ProductCreate, db: Session = Depends(get_db)):
    product = models.Product(**product_in.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product SKU already exists",
        ) from exc
    db.refresh(product)
    return product


@app.get("/products", response_model=list[schemas.ProductRead])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).order_by(models.Product.id).all()


@app.get("/products/{product_id}", response_model=schemas.ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return get_product_or_404(db, product_id)


@app.put("/products/{product_id}", response_model=schemas.ProductRead)
def update_product(product_id: int, product_in: schemas.ProductUpdate, db: Session = Depends(get_db)):
    product = get_product_or_404(db, product_id)
    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product SKU already exists",
        ) from exc
    db.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = get_product_or_404(db, product_id)
    db.delete(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is referenced by an order and cannot be deleted",
        ) from exc
    return None


@app.post("/customers", response_model=schemas.CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(customer_in: schemas.CustomerCreate, db: Session = Depends(get_db)):
    customer = models.Customer(**customer_in.model_dump())
    db.add(customer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer email already exists",
        ) from exc
    db.refresh(customer)
    return customer


@app.get("/customers", response_model=list[schemas.CustomerRead])
def list_customers(db: Session = Depends(get_db)):
    return db.query(models.Customer).order_by(models.Customer.id).all()


@app.get("/customers/{customer_id}", response_model=schemas.CustomerRead)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return get_customer_or_404(db, customer_id)


@app.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = get_customer_or_404(db, customer_id)
    db.delete(customer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer has orders and cannot be deleted",
        ) from exc
    return None


@app.post("/orders", response_model=schemas.OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(order_in: schemas.OrderCreate, db: Session = Depends(get_db)):
    get_customer_or_404(db, order_in.customer_id)

    requested_quantities: dict[int, int] = {}
    for item in order_in.items:
        requested_quantities[item.product_id] = requested_quantities.get(item.product_id, 0) + item.quantity

    products = (
        db.query(models.Product)
        .filter(models.Product.id.in_(requested_quantities.keys()))
        .with_for_update()
        .all()
    )
    products_by_id = {product.id: product for product in products}

    missing_ids = sorted(set(requested_quantities) - set(products_by_id))
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Products not found: {missing_ids}",
        )

    for product_id, requested_quantity in requested_quantities.items():
        product = products_by_id[product_id]
        if product.quantity_in_stock < requested_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient inventory for product {product_id}",
            )

    order = models.Order(customer_id=order_in.customer_id, total_amount=Decimal("0.00"))
    db.add(order)

    total_amount = Decimal("0.00")
    for product_id, requested_quantity in requested_quantities.items():
        product = products_by_id[product_id]
        unit_price = Decimal(product.price)
        line_total = unit_price * requested_quantity
        total_amount += line_total
        product.quantity_in_stock -= requested_quantity
        order.items.append(
            models.OrderItem(
                product_id=product_id,
                quantity=requested_quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    order.total_amount = total_amount
    db.commit()
    return (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .filter(models.Order.id == order.id)
        .one()
    )


@app.get("/orders", response_model=list[schemas.OrderRead])
def list_orders(db: Session = Depends(get_db)):
    return db.query(models.Order).options(selectinload(models.Order.items)).order_by(models.Order.id).all()


@app.get("/orders/{order_id}", response_model=schemas.OrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .filter(models.Order.id == order_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@app.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .filter(models.Order.id == order_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    for item in order.items:
        product = get_product_or_404(db, item.product_id)
        product.quantity_in_stock += item.quantity

    db.delete(order)
    db.commit()
    return None
