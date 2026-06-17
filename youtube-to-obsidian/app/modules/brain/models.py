from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class BrainSessionCreate(BaseModel):
    title: Optional[str] = None
    persona_id: Optional[int] = None
    is_clone_only: Optional[bool] = False

class BrainSessionResponse(BaseModel):
    id: int
    title: str
    persona_id: Optional[int] = None
    is_clone_only: int
    created_at: str
    updated_at: str

class BrainMessageCreate(BaseModel):
    content: str

class SourceDetail(BaseModel):
    title: str
    file_path: str
    similarity_score: float

class BrainMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    sources: Optional[List[SourceDetail]] = None
    tokens_input: int
    tokens_output: int
    cost_usd: float
    created_at: str

class SynthesisEstimateResponse(BaseModel):
    total_notes: int
    estimated_tokens: int
    estimated_cost_usd: float
