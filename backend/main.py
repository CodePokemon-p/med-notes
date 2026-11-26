import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from pinecone import Pinecone
from pydantic import BaseModel

load_dotenv()

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
INDEX_NAME = os.getenv("PINECONE_INDEX", "med-notes-ai")

# Create the index the first time: Pinecone hosts the embedding model for us
if not pc.has_index(INDEX_NAME):
    pc.create_index_for_model(
        name=INDEX_NAME,
        cloud="aws",
        region="us-east-1",  # the free plan supports this region
        embed={"model": "llama-text-embed-v2", "field_map": {"text": "text"}},
    )

desc = pc.describe_index(INDEX_NAME)
index = pc.Index(host=desc.host)
TEXT_FIELD = "text"  # the field name that holds the note text
NAMESPACE = "notes"  # a namespace is a folder inside the index

app = FastAPI(title="Med Notes API")


def get_user_id() -> str:
    # TEMPORARY: we replace this with the real Clerk user in the next step
    return "demo-user"


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
    # read a value whether the SDK gives us a dict or an object
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
            "filter": {"user_id": {"$eq": user_id}},  # only this user's notes
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