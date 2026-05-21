from typing import List, Optional
from pydantic import BaseModel, Field

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Nome do aplicativo")
    description: Optional[str] = Field(None, description="Descrição do aplicativo")

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: str

class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Título da subtarefa")
    status: str = Field("pending", description="Status da subtarefa: 'pending' ou 'completed'")

class SubtaskResponse(BaseModel):
    id: int
    phase_id: int
    title: str
    status: str

class PhaseCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Título da fase/etapa")
    description: Optional[str] = Field(None, description="Descrição detalhada")
    status: str = Field("pending", description="Status da fase: 'pending' ou 'completed'")
    pos_x: float = Field(100.0, description="Posição X no canvas")
    pos_y: float = Field(100.0, description="Posição Y no canvas")

class PhaseResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: Optional[str] = None
    status: str
    pos_x: float
    pos_y: float
    subtasks: List[SubtaskResponse] = Field(default_factory=list)

class ConnectionCreate(BaseModel):
    from_phase_id: int = Field(..., description="ID da fase de origem")
    to_phase_id: int = Field(..., description="ID da fase de destino")

class ConnectionResponse(BaseModel):
    id: int
    project_id: int
    from_phase_id: int
    to_phase_id: int

class PhasePosition(BaseModel):
    id: int
    pos_x: float
    pos_y: float

class CanvasSyncPayload(BaseModel):
    positions: List[PhasePosition] = Field(default_factory=list, description="Lista de posições das fases a atualizar")
    connections: List[ConnectionCreate] = Field(default_factory=list, description="Lista final de conexões (setas) do canvas")
