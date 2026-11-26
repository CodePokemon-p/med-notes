import base64
import os
import uuid

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jwt import PyJWKClient
from pinecone import Pinecone
from pydantic import BaseModel

load_dotenv()

# ---------- Pinecone ----------
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
INDEX_NAME = os.getenv("PINECONE_INDEX", "med-notes-ai")

if not pc.has_index(INDEX_NAME):
    pc.create_index_for_model(
        name=INDEX_NAME,
        cloud="aws",
        region="us-east-1",
        embed={"model": "llama-text-embed-v2", "field_map": {"text": "text"}},
    )

desc = pc.describe_index(INDEX_NAME)
index = pc.Index(host=desc.host)
TEXT_FIELD = "text"
NAMESPACE = "notes"

# ---------- Clerk token checking ----------
# The publishable key secretly contains your Clerk domain (base64-encoded).
_pk = os.environ["CLERK_PUBLISHABLE_KEY"]
_encoded = _pk.split("_", 2)[2]
_encoded += "=" * (-len(_encoded) % 4)
CLERK_DOMAIN = base64.b64decode(_encoded).decode().rstrip("$")
ISSUER = f"https://{CLERK_DOMAIN}"
jwks_client = PyJWKClient(f"{ISSUER}/.well-known/jwks.json")


def get_user_id(authorization: str = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=ISSUER,
            leeway=10,
            options={"verify_aud": False},
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return claims["sub"]  # the real Clerk user id


# ---------- App ----------
app = FastAPI(title="Med Notes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoteIn(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/notes")
def add_note(note: NoteIn, user_id: str = Depends(get_user_id)):
    note_id = str(uuid.uuid4())
    index.upsert_records(
        namespace=NAMESPACE,
        records=[{"_id": note_id, TEXT_FIELD: note.text, "user_id": user_id}],
    )
    return {"id": note_id, "saved": True}


def _get(obj, *names):
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


@app.get("/search")
def search_notes(q: str, top_k: int = 3, user_id: str = Depends(get_user_id)):
    results = index.search(
        namespace=NAMESPACE,
        query={
            "top_k": top_k,
            "inputs": {"text": q},
            "filter": {"user_id": {"$eq": user_id}},
        },
    )
    output = []
    for h in results.result.hits:
        fields = _get(h, "fields") or {}
        output.append(
            {
                "id": _get(h, "_id", "id"),
                "score": _get(h, "_score", "score"),
                "text": _get(fields, TEXT_FIELD),
            }
        )
    return output