from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    # When set, retrieval is limited to this document. The UI sets it after an
    # upload so a visitor's own PDF isn't answered from the demo corpus.
    document_id: str | None = None
