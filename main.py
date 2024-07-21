from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, String, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from uuid import uuid4

DATABASE_URL = "postgresql+asyncpg://user:Melvin@123@localhost/db"
MONGO_DB_URL = "mongodb://localhost:27017/"

Base = declarative_base()
app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

mongodb_client = AsyncIOMotorClient(MONGO_DB_URL)
mongodb = mongodb_client["user_db"]

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    first_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    phone = Column(String)

class UserCreate(BaseModel):
    first_name: str
    email: EmailStr
    password: str = Field(min_length=6)
    phone: str
    profile_picture: UploadFile

class UserRead(BaseModel):
    id: str
    first_name: str
    email: EmailStr
    phone: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register", response_model=UserRead)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if the email already exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password
    hashed_password = pwd_context.hash(user.password)

    # Create a new user
    user_id = str(uuid4())
    db_user = User(
        id=user_id,
        first_name=user.first_name,
        email=user.email,
        password=hashed_password,
        phone=user.phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Save profile picture to MongoDB
    profile_picture_data = await user.profile_picture.read()
    await mongodb["profile_pictures"].insert_one({
        "user_id": user_id,
        "profile_picture": profile_picture_data
    })

    return UserRead(
        id=user_id,
        first_name=user.first_name,
        email=user.email,
        phone=user.phone
    )

@app.get("/user/{user_id}", response_model=UserRead)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserRead(
        id=db_user.id,
        first_name=db_user.first_name,
        email=db_user.email,
        phone=db_user.phone
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
