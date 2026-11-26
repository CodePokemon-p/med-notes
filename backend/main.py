import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from pinecone import Pinecone
from pydantic import BaseModel

load_dotenv()

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
INDEX_NAME = os.getenv("PINECONE_INDEX", "med-notes")

# Ask Pinecone about our index: its address (host) and which field holds the text
desc = pc.describe_index(INDEX_NAME)
index = pc.Index(host=desc.host)
TEXT_FIELD = desc.to_dict()["embed"]["field_map"]["text"]
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
    hits = results["result"]["hits"]
    return [
        {"id": h["_id"], "score": h["_score"], "text": h["fields"].get(TEXT_FIELD)}
        for h in hits
    ]