import os
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, func, or_, select, text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mssql+pyodbc://@localhost/AvitoClone?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&TrustServerCertificate=yes",
)
engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Advertisement(Base):
    __tablename__ = "advertisements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="активно")
    date: Mapped[datetime] = mapped_column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))


class PurchaseTransaction(Base):
    __tablename__ = "purchase_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertisement_id: Mapped[int] = mapped_column(ForeignKey("advertisements.id"), nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, examples=["Иван"])
    email: str = Field(min_length=3, max_length=100, examples=["ivan@example.com"])
    phone: str | None = Field(default=None, max_length=20)


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class AdvertisementCreate(BaseModel):
    owner_id: int = Field(gt=0, examples=[1])
    title: str = Field(min_length=1, max_length=100, examples=["Велосипед"])
    text: str = Field(min_length=1, examples=["В хорошем состоянии"])
    price: int = Field(ge=0, examples=[15000])
    status: str = Field(default="активно", max_length=20)


class AdvertisementUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1)
    price: int = Field(ge=0)
    status: str = Field(max_length=20)


with engine.begin() as connection:
    if engine.dialect.name == "mssql":
        connection.execute(sql_text("""
            IF COL_LENGTH('dbo.users', 'balance') IS NULL
                ALTER TABLE dbo.users ADD balance INT NOT NULL CONSTRAINT DF_users_balance DEFAULT 0;
        """))
    elif engine.dialect.name == "sqlite":
        columns = connection.execute(sql_text("PRAGMA table_info(users)" )).fetchall()
        if not any(column[1] == "balance" for column in columns):
            connection.execute(sql_text("ALTER TABLE users ADD COLUMN balance INTEGER NOT NULL DEFAULT 0"))
Base.metadata.create_all(engine)
app = FastAPI(
    title="Avito Shtuka API",
    description="API сервиса объявлений на FastAPI и SQLAlchemy",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return FileResponse("static/index.html", headers={"Cache-Control": "no-store"})

def check_entity_exists(db: Session, table: str, entity_id: int):
    query = sql_text(f"SELECT id FROM {table} WHERE id = :id")
    result = db.execute(query, {"id": entity_id}).fetchone()
    if not result:
        name = "Пользователь" if table == "users" else "Объявление"
        raise HTTPException(status_code=404, detail=f"{name} не найден")


def row_to_dict(row, keys):
    return dict(zip(keys, row)) if row else None

@app.post("/api/users")
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.execute(select(User).where(User.email == user_data.email)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    user = User(name=user_data.name, email=user_data.email, phone=user_data.phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone, "balance": user.balance}


@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    users = db.execute(select(User).order_by(User.name, User.id)).scalars().all()
    return [{"id": user.id, "name": user.name, "balance": user.balance} for user in users]


@app.get("/api/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"id": user.id, "name": user.name, "email": user.email,
            "phone": user.phone, "balance": user.balance}


@app.post("/api/users/{user_id}/balance")
def add_balance(user_id: int, amount: int = Query(..., gt=0), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.balance += amount
    db.commit()
    db.refresh(user)
    return {"user_id": user_id, "balance": user.balance}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    duplicate = db.execute(select(User).where(User.email == user_data.email, User.id != user_id)).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    user.name = user_data.name
    user.email = user_data.email
    user.phone = user_data.phone
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db.delete(user)
    db.commit()
    return {"message": "Пользователь успешно удален"}

@app.post("/api/ads")
def create_ad(ad_data: AdvertisementCreate, db: Session = Depends(get_db)):
    owner = db.get(User, ad_data.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Продавец не найден")
    ad = Advertisement(**ad_data.model_dump())
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return {"id": ad.id, "owner_id": ad.owner_id, "title": ad.title,
            "text": ad.text, "price": ad.price, "status": ad.status}


@app.get("/api/ads")
def get_ads(
    search: str | None = Query(None, description="Поиск по названию и описанию"),
    status: str | None = Query(None, description="Фильтр по статусу"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(6, ge=1, le=100, description="Количество объявлений на странице"),
    db: Session = Depends(get_db),
):
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Advertisement.title.like(pattern), Advertisement.text.like(pattern)))
    if status:
        filters.append(Advertisement.status == status)

    total_query = select(func.count(Advertisement.id)).where(*filters)
    total = db.execute(total_query).scalar_one()
    skip = (page - 1) * limit
    ads_query = (
        select(Advertisement, User.name)
        .join(User, Advertisement.owner_id == User.id)
        .where(*filters)
        .order_by(Advertisement.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = db.execute(ads_query).all()
    return {
        "items": [
            {"id": ad.id, "owner_id": ad.owner_id, "title": ad.title, "text": ad.text,
             "price": ad.price, "status": ad.status, "date": ad.date, "seller_name": seller_name}
            for ad, seller_name in rows
        ],
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
    }


@app.get("/api/ads/{ad_id}")
def get_ad(ad_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(Advertisement, User.name)
        .join(User, Advertisement.owner_id == User.id)
        .where(Advertisement.id == ad_id)
    ).first()
    ad = row[0] if row else None
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return {"id": ad.id, "owner_id": ad.owner_id, "title": ad.title, "text": ad.text,
            "price": ad.price, "status": ad.status, "date": ad.date, "seller_name": row[1]}


@app.put("/api/ads/{ad_id}")
def update_ad(ad_id: int, ad_data: AdvertisementUpdate, db: Session = Depends(get_db)):
    ad = db.get(Advertisement, ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    ad.title = ad_data.title
    ad.text = ad_data.text
    ad.price = ad_data.price
    ad.status = ad_data.status
    db.commit()
    db.refresh(ad)
    return {"id": ad.id, "owner_id": ad.owner_id, "title": ad.title,
            "text": ad.text, "price": ad.price, "status": ad.status}


@app.delete("/api/ads/{ad_id}")
def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.get(Advertisement, ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    db.delete(ad)
    db.commit()
    return {"message": "Объявление успешно удалено"}


@app.post("/api/purchases")
def purchase_ad(
    advertisement_id: int = Query(..., description="ID объявления"),
    buyer_id: int = Query(..., description="ID покупателя"),
    db: Session = Depends(get_db),
):
    try:
        lock = " WITH (UPDLOCK, ROWLOCK)" if engine.dialect.name == "mssql" else ""
        ad = db.execute(sql_text(f"""
            SELECT id, owner_id, price, status
            FROM advertisements{lock}
            WHERE id = :advertisement_id
        """), {"advertisement_id": advertisement_id}).fetchone()
        if not ad:
            raise HTTPException(status_code=404, detail="Объявление не найдено")
        if ad.status != "активно" and ad.status != "active":
            raise HTTPException(status_code=400, detail="Объявление уже нельзя купить")
        if ad.owner_id == buyer_id:
            raise HTTPException(status_code=400, detail="Нельзя купить собственное объявление")

        buyer = db.execute(sql_text(f"SELECT id, balance FROM users{lock} WHERE id = :buyer_id"),
                           {"buyer_id": buyer_id}).fetchone()
        seller = db.execute(sql_text(f"SELECT id, balance FROM users{lock} WHERE id = :seller_id"),
                            {"seller_id": ad.owner_id}).fetchone()
        if not buyer:
            raise HTTPException(status_code=404, detail="Покупатель не найден")
        if not seller:
            raise HTTPException(status_code=404, detail="Продавец не найден")
        if buyer.balance < ad.price:
            raise HTTPException(status_code=400, detail="Недостаточно денег на балансе покупателя")

        db.execute(sql_text("UPDATE users SET balance = balance - :amount WHERE id = :buyer_id"),
                   {"amount": ad.price, "buyer_id": buyer_id})
        db.execute(sql_text("UPDATE users SET balance = balance + :amount WHERE id = :seller_id"),
                   {"amount": ad.price, "seller_id": ad.owner_id})
        db.execute(sql_text("UPDATE advertisements SET status = 'sold' WHERE id = :ad_id"),
                   {"ad_id": advertisement_id})
        transaction = db.execute(sql_text("""
            INSERT INTO purchase_transactions
                (advertisement_id, buyer_id, seller_id, amount, status)
            OUTPUT INSERTED.id
            VALUES (:advertisement_id, :buyer_id, :seller_id, :amount, 'completed')
        """ if engine.dialect.name == "mssql" else """
            INSERT INTO purchase_transactions
                (advertisement_id, buyer_id, seller_id, amount, status)
            VALUES (:advertisement_id, :buyer_id, :seller_id, :amount, 'completed')
        """), {"advertisement_id": advertisement_id, "buyer_id": buyer_id,
               "seller_id": ad.owner_id, "amount": ad.price})
        transaction_id = transaction.scalar_one() if engine.dialect.name == "mssql" else db.execute(
            sql_text("SELECT last_insert_rowid()")).scalar_one()
        db.commit()
        return {"transaction_id": transaction_id, "advertisement_id": advertisement_id,
                "buyer_id": buyer_id, "seller_id": ad.owner_id, "amount": ad.price,
                "status": "completed"}
    except Exception:
        db.rollback()
        raise


@app.get("/api/transactions")
def get_transactions(user_id: int = Query(..., description="ID пользователя"), db: Session = Depends(get_db)):
    rows = db.execute(sql_text("""
        SELECT t.id, t.advertisement_id, a.title AS advertisement_title,
               t.buyer_id, buyer.name AS buyer_name,
               t.seller_id, seller.name AS seller_name,
               t.amount, t.status, t.created_at
        FROM purchase_transactions t
        JOIN advertisements a ON a.id = t.advertisement_id
        JOIN users buyer ON buyer.id = t.buyer_id
        JOIN users seller ON seller.id = t.seller_id
        WHERE t.buyer_id = :user_id OR t.seller_id = :user_id
        ORDER BY t.id DESC
    """), {"user_id": user_id}).fetchall()
    return [row_to_dict(row, ["id", "advertisement_id", "advertisement_title", "buyer_id", "buyer_name",
                              "seller_id", "seller_name", "amount", "status", "created_at"])
            for row in rows]
