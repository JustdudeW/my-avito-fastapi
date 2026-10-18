from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "sqlite:///./avito.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

with engine.connect() as connection:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            phone VARCHAR(20)
        );
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS advertisements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title VARCHAR(100) NOT NULL,
            text TEXT NOT NULL,
            price INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'активно',
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
        );
    """))
    connection.commit()
app = FastAPI(title="My Avito API (Pure SQL)")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"status": "success", "message": "Добро пожаловать в My Avito API на чистом SQL"}

def check_entity_exists(db: Session, table: str, entity_id: int):
    query = text(f"SELECT id FROM {table} WHERE id = :id")
    result = db.execute(query, {"id": entity_id}).fetchone()
    if not result:
        name = "Пользователь" if table == "users" else "Объявление"
        raise HTTPException(status_code=404, detail=f"{name} не найден")


def row_to_dict(row, keys):
    return dict(zip(keys, row)) if row else None

@app.post("/api/users")
def create_user(name: str, email: str, phone: str = None, db: Session = Depends(get_db)):
    if db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    result = db.execute(text("INSERT INTO users (name, email, phone) VALUES (:name, :email, :phone)"),
                        {"name": name, "email": email, "phone": phone})
    db.commit()
    return {"id": result.lastrowid, "name": name, "email": email, "phone": phone}


@app.get("/api/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(text("SELECT id, name, email, phone FROM users WHERE id = :user_id"),
                      {"user_id": user_id}).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return row_to_dict(user, ["id", "name", "email", "phone"])


@app.put("/api/users/{user_id}")
def update_user(user_id: int, name: str, email: str, phone: str = None, db: Session = Depends(get_db)):
    check_entity_exists(db, "users", user_id)
    db.execute(text("UPDATE users SET name = :name, email = :email, phone = :phone WHERE id = :user_id"),
               {"name": name, "email": email, "phone": phone, "user_id": user_id})
    db.commit()
    return {"id": user_id, "name": name, "email": email, "phone": phone}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    check_entity_exists(db, "users", user_id)
    db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
    db.commit()
    return {"message": "Пользователь успешно удален"}

@app.post("/api/ads")
def create_ad(owner_id: int, title: str, text_content: str, price: int, status: str = "активно",
              db: Session = Depends(get_db)):
    check_entity_exists(db, "users", owner_id)

    result = db.execute(text(
        "INSERT INTO advertisements (owner_id, title, text, price, status) VALUES (:owner_id, :title, :text, :status)"),
                        {"owner_id": owner_id, "title": title, "text": text_content, "price": price, "status": status})
    db.commit()
    return {"id": result.lastrowid, "owner_id": owner_id, "title": title, "text": text_content, "price": price,
            "status": status}


@app.get("/api/ads")
def get_ads(status: str = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1),
            db: Session = Depends(get_db)):
    skip = (page - 1) * limit
    sql = "SELECT id, owner_id, title, text, price, status, date FROM advertisements"
    params = {"limit": limit, "offset": skip}

    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " LIMIT :limit OFFSET :offset"

    result = db.execute(text(sql), params).fetchall()
    keys = ["id", "owner_id", "title", "text", "price", "status", "date"]
    return [row_to_dict(row, keys) for row in result]


@app.get("/api/ads/{ad_id}")
def get_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.execute(text("SELECT id, owner_id, title, text, price, status, date FROM advertisements WHERE id = :ad_id"),
                    {"ad_id": ad_id}).fetchone()
    if not ad:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return row_to_dict(ad, ["id", "owner_id", "title", "text", "price", "status", "date"])


@app.put("/api/ads/{ad_id}")
def update_ad(ad_id: int, title: str, text_content: str, price: int, status: str, db: Session = Depends(get_db)):
    check_entity_exists(db, "advertisements", ad_id)
    db.execute(text(
        "UPDATE advertisements SET title = :title, text = :text, price = :price, status = :status WHERE id = :ad_id"),
               {"title": title, "text": text_content, "price": price, "status": status, "ad_id": ad_id})
    db.commit()
    return {"id": ad_id, "title": title, "text": text_content, "price": price, "status": status}


@app.delete("/api/ads/{ad_id}")
def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    check_entity_exists(db, "advertisements", ad_id)
    db.execute(text("DELETE FROM advertisements WHERE id = :ad_id"), {"ad_id": ad_id})
    db.commit()
    return {"message": "Объявление успешно удалено"}
