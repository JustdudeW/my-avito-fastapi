from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, String, Text, Integer, ForeignKey, select, update, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
engine = create_engine("sqlite:///avito.db", echo=True)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    items: Mapped[List["Item"]] = relationship(back_populates="seller", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    seller: Mapped["User"] = relationship(back_populates="items")

Base.metadata.create_all(engine)

if __name__ == "__main__":
    with Session(engine) as session:

        print("CREATE: Создание пользователей и объявлений")
        seller_1 = User(name="Алексей", phone="+79991112233")
        session.add(seller_1)
        session.flush()
        item_1 = Item(title="iPhone 13 Pro 128GB", price=55000, description="Отличном состоянии, без сколов",
                      seller_id=seller_1.id)
        item_2 = Item(title="Игровой ПК RTX 3060", price=70000, description="Тянет все игры на ультра",
                      seller_id=seller_1.id)

        session.add_all([item_1, item_2])
        session.commit()
        print("Данные успешно добавлены!")

        print("READ: Чтение данных")
        item = session.get(Item, 1)
        if item:
            print(f"Найдено объявление: {item.title} за {item.price} руб. Продавец: {item.seller.name}")
        stmt = select(Item).where(Item.price >= 60000)
        expensive_items = session.execute(stmt).scalars().all()
        print("Дорогие товары:")
        for i in expensive_items:
            print(f"- {i.title} ({i.price} руб.)")

        print("UPDATE: Обновление данных")
        item_to_update = session.get(Item, 1)
        if item_to_update:
            item_to_update.price = 50000
            session.commit()
            print(f"Цена на {item_to_update.title} успешно снижена до {item_to_update.price}")

        print("DELETE: Удаление данных")
        item_to_delete = session.get(Item, 2)
        if item_to_delete:
            session.delete(item_to_delete)
            session.commit()
            print("Объявление с ПК удалено с Авито.")
