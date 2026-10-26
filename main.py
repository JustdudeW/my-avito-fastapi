import os
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, text as sql_text
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
def create_user(name: str, email: str, phone: str = None, db: Session = Depends(get_db)):
    if db.execute(sql_text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    result = db.execute(sql_text("INSERT INTO users (name, email, phone) VALUES (:name, :email, :phone)"),
                        {"name": name, "email": email, "phone": phone})
    db.commit()
    user_id = db.execute(sql_text("SELECT id FROM users WHERE email = :email"), {"email": email}).scalar_one()
    return {"id": user_id, "name": name, "email": email, "phone": phone}


@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    rows = db.execute(sql_text("SELECT id, name, balance FROM users ORDER BY name, id")).fetchall()
    return [row_to_dict(row, ["id", "name", "balance"]) for row in rows]


@app.get("/api/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(sql_text("SELECT id, name, email, phone, balance FROM users WHERE id = :user_id"),
                      {"user_id": user_id}).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return row_to_dict(user, ["id", "name", "email", "phone", "balance"])


@app.post("/api/users/{user_id}/balance")
def add_balance(user_id: int, amount: int = Query(..., gt=0), db: Session = Depends(get_db)):
    check_entity_exists(db, "users", user_id)
    db.execute(sql_text("UPDATE users SET balance = balance + :amount WHERE id = :user_id"),
               {"amount": amount, "user_id": user_id})
    db.commit()
    balance = db.execute(sql_text("SELECT balance FROM users WHERE id = :user_id"), {"user_id": user_id}).scalar_one()
    return {"user_id": user_id, "balance": balance}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, name: str, email: str, phone: str = None, db: Session = Depends(get_db)):
    check_entity_exists(db, "users", user_id)
    db.execute(sql_text("UPDATE users SET name = :name, email = :email, phone = :phone WHERE id = :user_id"),
               {"name": name, "email": email, "phone": phone, "user_id": user_id})
    db.commit()
    return {"id": user_id, "name": name, "email": email, "phone": phone}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    check_entity_exists(db, "users", user_id)
    db.execute(sql_text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
    db.commit()
    return {"message": "Пользователь успешно удален"}

@app.post("/api/ads")
def create_ad(owner_id: int, title: str, text_content: str, price: int, status: str = "активно",
              db: Session = Depends(get_db)):
    check_entity_exists(db, "users", owner_id)

    result = db.execute(sql_text(
        "INSERT INTO advertisements (owner_id, title, text, price, status) VALUES (:owner_id, :title, :text, :price, :status)"),
                        {"owner_id": owner_id, "title": title, "text": text_content, "price": price, "status": status})
    db.commit()
    ad_id = db.execute(sql_text(
        "SELECT TOP 1 id FROM advertisements WHERE owner_id = :owner_id AND title = :title ORDER BY id DESC"),
        {"owner_id": owner_id, "title": title}).scalar_one()
    return {"id": ad_id, "owner_id": owner_id, "title": title, "text": text_content, "price": price,
            "status": status}


@app.get("/api/ads")
def get_ads(
    search: str | None = Query(None, description="Поиск по названию и описанию"),
    status: str | None = Query(None, description="Фильтр по статусу"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(6, ge=1, le=100, description="Количество объявлений на странице"),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * limit
    conditions = []
    params = {"limit": limit, "offset": skip}

    if search:
        conditions.append("(title LIKE :search OR text LIKE :search)")
        params["search"] = f"%{search.strip()}%"
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    total = db.execute(sql_text(f"SELECT COUNT(*) FROM advertisements{where_sql}"), params).scalar_one()
    sql = f"""
        SELECT a.id, a.owner_id, a.title, a.text, a.price, a.status, a.date, u.name AS seller_name
        FROM advertisements a
        JOIN users u ON u.id = a.owner_id
        {where_sql.replace('title', 'a.title').replace('text', 'a.text').replace('status', 'a.status')}
    """
    if engine.dialect.name == "mssql":
        sql += " ORDER BY a.id DESC OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    else:
        sql += " ORDER BY a.id DESC LIMIT :limit OFFSET :offset"

    result = db.execute(sql_text(sql), params).fetchall()
    keys = ["id", "owner_id", "title", "text", "price", "status", "date", "seller_name"]
    return {
        "items": [row_to_dict(row, keys) for row in result],
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
    }


@app.get("/api/ads/{ad_id}")
def get_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.execute(sql_text("SELECT id, owner_id, title, text, price, status, date FROM advertisements WHERE id = :ad_id"),
                    {"ad_id": ad_id}).fetchone()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return row_to_dict(ad, ["id", "owner_id", "title", "text", "price", "status", "date"])


@app.put("/api/ads/{ad_id}")
def update_ad(ad_id: int, title: str, text_content: str, price: int, status: str, db: Session = Depends(get_db)):
    check_entity_exists(db, "advertisements", ad_id)
    db.execute(sql_text(
        "UPDATE advertisements SET title = :title, text = :text, price = :price, status = :status WHERE id = :ad_id"),
               {"title": title, "text": text_content, "price": price, "status": status, "ad_id": ad_id})
    db.commit()
    return {"id": ad_id, "title": title, "text": text_content, "price": price, "status": status}


@app.delete("/api/ads/{ad_id}")
def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    check_entity_exists(db, "advertisements", ad_id)
    db.execute(sql_text("DELETE FROM advertisements WHERE id = :ad_id"), {"ad_id": ad_id})
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
