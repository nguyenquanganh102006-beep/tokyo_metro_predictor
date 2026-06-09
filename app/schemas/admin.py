from pydantic import BaseModel
from typing import Optional

class BanStationRequest(BaseModel):
    station_id: str
    reason: Optional[str] = None

class BanLineRequest(BaseModel):
    line_id: str
    reason: Optional[str] = None

class BanEdgeRequest(BaseModel):
    edge_id: int
    reason: Optional[str] = None

class StatusResponse(BaseModel):
    success: bool
    message: str
