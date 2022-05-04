from uuid import UUID, uuid4

from fastapi import Depends, FastAPI

from .auth import authenticate, authorize
from .crud import create_key_in_db, delete_key_in_db, get_db, get_key_in_db
from .errors import Forbidden
from .logs import *  # noqa: F403, E402, F401
from .models import APIKeyModel, APIKeyModelCreated, TokenCreated, TokenScope
from .tokens import encode

app = FastAPI()


@app.get("/health")
async def health() -> None:
    return "ok", 200


@app.get("/create-root-key", status_code=201, response_model=APIKeyModelCreated)
async def rootkey(db=Depends(get_db)) -> None:
    key = APIKeyModel(
        tenant=uuid4(),
        user_id=str(uuid4()),
        scopes=[
            TokenScope(resource="keys", action="read"),
            TokenScope(resource="keys", action="write"),
        ],
    )
    record, secret = create_key_in_db(db, key)
    return {"secret": secret, **record.__dict__}


@app.get("/api/v0/tokens", response_model=TokenCreated)
async def create_token(authctx=Depends(authenticate)) -> None:
    return {"token": encode(identity=authctx.identity, scopes=authctx.scopes)}


@app.post("/api/v0/keys", status_code=201, response_model=APIKeyModelCreated)
async def create_key(key: APIKeyModel, db=Depends(get_db), authctx=Depends(authenticate)) -> None:

    authorize(authctx.scopes, TokenScope(resource="keys", action="write"))

    if key.tenant is None:
        key.tenant = authctx.identity.tenant
    elif key.tenant != authctx.identity.tenant:
        raise Forbidden()

    record, secret = create_key_in_db(db, key)
    return {"secret": secret, **record.__dict__}


@app.get("/api/v0/keys/{_id}", response_model=APIKeyModel)
async def get_key(_id: UUID, db=Depends(get_db), authctx=Depends(authenticate)) -> None:
    authorize(authctx.scopes, TokenScope(resource="keys", action="read"))
    record = get_key_in_db(db, _id)
    return record


@app.delete("/api/v0/keys/{_id}", response_model=APIKeyModel)
async def delete_key(
    _id: UUID, hard: bool = False, db=Depends(get_db), authctx=Depends(authenticate)
) -> None:
    authorize(authctx.scopes, TokenScope(resource="keys", action="write"))
    record = delete_key_in_db(db, _id, hard)
    return record
