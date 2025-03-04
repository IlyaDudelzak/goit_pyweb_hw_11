from datetime import date, timedelta
from typing import Optional, List
import os

from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Date, Text, or_
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv

# Завантаження змінних середовища з файлу .env
load_dotenv()

# Отримання окремих параметрів для PostgreSQL з .env
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")  # за замовчуванням 5432
POSTGRES_DB = os.getenv("POSTGRES_DB")

if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB]):
    raise Exception("Не всі параметри для PostgreSQL задані у файлі .env")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy модель для контактів
class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, nullable=False)
    birthday = Column(Date, nullable=False)
    additional_info = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

# Pydantic схеми для валідації даних
class ContactBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str
    birthday: date
    additional_info: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]
    birthday: Optional[date]
    additional_info: Optional[str]

class ContactOut(ContactBase):
    id: int

    class Config:
        from_attributes = True  # Замість orm_mode = True

# Залежність для отримання сесії роботи з базою даних
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(
    title="Контактний API",
    description="API для зберігання та управління контактами",
    version="1.0.0"
)

@app.post("/contacts/", response_model=ContactOut)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    db_contact = Contact(**contact.dict())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@app.get("/contacts/", response_model=List[ContactOut])
def read_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    contacts = db.query(Contact).offset(skip).limit(limit).all()
    return contacts

@app.get("/contacts/{contact_id}", response_model=ContactOut)
def read_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Контакт не знайдено")
    return contact

@app.put("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, contact_update: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Контакт не знайдено")
    for key, value in contact_update.dict(exclude_unset=True).items():
        setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return contact

@app.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Контакт не знайдено")
    db.delete(contact)
    db.commit()
    return {"detail": "Контакт успішно видалено"}

@app.get("/contacts/search/", response_model=List[ContactOut])
def search_contacts(query: str = Query(..., description="Пошуковий запит за ім'ям, прізвищем або email"), 
                    db: Session = Depends(get_db)):
    contacts = db.query(Contact).filter(
        or_(
            Contact.first_name.ilike(f"%{query}%"),
            Contact.last_name.ilike(f"%{query}%"),
            Contact.email.ilike(f"%{query}%")
        )
    ).all()
    return contacts

@app.get("/contacts/upcoming-birthdays/", response_model=List[ContactOut])
def upcoming_birthdays(db: Session = Depends(get_db)):
    today = date.today()
    upcoming = today + timedelta(days=7)
    contacts = db.query(Contact).all()
    result = []
    for contact in contacts:
        try:
            bday_this_year = contact.birthday.replace(year=today.year)
        except ValueError:
            bday_this_year = contact.birthday.replace(year=today.year, day=today.day-1)
        if bday_this_year < today:
            bday_this_year = contact.birthday.replace(year=today.year + 1)
        if today <= bday_this_year <= upcoming:
            result.append(contact)
    return result
