from base64 import b64encode
from datetime import datetime as dt
from datetime import timezone as tz
from hashlib import pbkdf2_hmac
from os import environ, urandom
from typing import Tuple
from uuid import UUID, uuid4

from sqlalchemy import Column, create_engine
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import JSON, TIMESTAMP

from .errors import NotFound
from .models import APIKeyModel, APIKeyStatus

POSTGRES_USER = environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASS = environ.get("POSTGRES_PASS", "postgres")
POSTGRES_HOST = environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = environ.get("POSTGRES_PORT", "5432")
POSTGRES_NAME = environ.get("POSTGRES_NAME", "postgres")

POSTGRES_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASS}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_NAME}"

SECRET_BYTES = 32
HMAC_SALT_BYTES = 32

engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def now() -> dt:
    """Get the current UTC time. Returns TZ-aware timestamp."""
    return dt.now(tz.utc)


class APIKeyRecord(Base):
    __tablename__ = "apikeys"

    key_id = Column(
        SQLUUID(as_uuid=True), default=uuid4, primary_key=True, unique=True, nullable=False
    )
    hmac = Column(String(), nullable=False)
    salt = Column(String(), nullable=False)
    tenant = Column(SQLUUID(as_uuid=True), default=None, nullable=True)
    user_id = Column(String(), default=None, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=now)
    updated_at = Column(TIMESTAMP(timezone=True), default=now, onupdate=now, nullable=True)
    revoked_at = Column(TIMESTAMP(timezone=True), default=None, nullable=True)
    status = Column(SQLEnum(APIKeyStatus), default=APIKeyStatus.ACTIVE)
    scopes = Column(JSON, default=[], nullable=True)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_secret() -> bytes:
    return b64encode(urandom(SECRET_BYTES))


def compute_hmac(_id: bytes, secret: bytes, salt: bytes = None) -> bytes:
    message = _id + secret
    if salt is None:
        salt = urandom(HMAC_SALT_BYTES)
    return pbkdf2_hmac("sha256", message, salt, 100000), salt


def create_key_in_db(db: Session, key: APIKeyModel) -> Tuple[APIKeyRecord, bytes]:

    key.key_id = uuid4()
    secret = urandom(SECRET_BYTES)
    hmac, salt = compute_hmac(key.key_id.bytes, secret)

    record = APIKeyRecord(
        hmac=b64encode(hmac).decode(), salt=b64encode(salt).decode(), **key.dict()
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record, b64encode(secret).decode()


def get_key_in_db(db: Session, _id: UUID) -> APIKeyRecord:
    result = db.query(APIKeyRecord).filter(APIKeyRecord.key_id == _id).first()
    if result is None:
        raise NotFound()
    return result


def delete_key_in_db(db: Session, _id: UUID, hard: bool = False) -> APIKeyRecord:
    key = get_key_in_db(db, _id)
    if hard:
        db.delete(key)
    else:
        key.status = APIKeyStatus.REVOKED
        key.revoked_at = now()
        db.add(key)
    db.commit()
    return key
