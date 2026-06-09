from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.models.subway import Station, Line, Edge
from app.schemas.admin import BanStationRequest, BanLineRequest, BanEdgeRequest, StatusResponse

router = APIRouter()


def _matching_edges(db: Session, edge: Edge):
    return (
        db.query(Edge)
        .filter(
            (
                (Edge.source_id == edge.source_id)
                & (Edge.target_id == edge.target_id)
            )
            | (
                (Edge.source_id == edge.target_id)
                & (Edge.target_id == edge.source_id)
            )
        )
        .all()
    )


@router.post("/station/ban", response_model=StatusResponse)
def ban_station(req: BanStationRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    station = db.query(Station).filter(Station.station_id == req.station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station khong ton tai")
    station.is_active = False
    db.commit()
    return StatusResponse(success=True, message=f"Da dong ga {station.station_name}")


@router.post("/station/unban", response_model=StatusResponse)
def unban_station(req: BanStationRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    station = db.query(Station).filter(Station.station_id == req.station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station khong ton tai")
    station.is_active = True
    db.commit()
    return StatusResponse(success=True, message=f"Da mo lai ga {station.station_name}")


@router.post("/line/ban", response_model=StatusResponse)
def ban_line(req: BanLineRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    line = db.query(Line).filter(Line.line_id == req.line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Tuyen khong ton tai")
    line.is_active = False
    db.query(Station).filter(Station.line_id == req.line_id).update({"is_active": False})
    db.commit()
    return StatusResponse(success=True, message=f"Da cam toan bo tuyen {line.line_name}")


@router.post("/line/unban", response_model=StatusResponse)
def unban_line(req: BanLineRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    line = db.query(Line).filter(Line.line_id == req.line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Tuyen khong ton tai")
    line.is_active = True
    db.query(Station).filter(Station.line_id == req.line_id).update({"is_active": True})
    db.commit()
    return StatusResponse(success=True, message=f"Da mo lai toan bo tuyen {line.line_name}")


@router.post("/edge/ban", response_model=StatusResponse)
def ban_edge(req: BanEdgeRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    edge = db.query(Edge).filter(Edge.edge_id == req.edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Canh khong ton tai")

    matching_edges = _matching_edges(db, edge)
    for matching_edge in matching_edges:
        matching_edge.is_active = False

    db.commit()
    return StatusResponse(
        success=True,
        message=f"Da cam {len(matching_edges)} canh giua {edge.source_id} va {edge.target_id}",
    )


@router.post("/edge/unban", response_model=StatusResponse)
def unban_edge(req: BanEdgeRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    edge = db.query(Edge).filter(Edge.edge_id == req.edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Canh khong ton tai")

    matching_edges = _matching_edges(db, edge)
    for matching_edge in matching_edges:
        matching_edge.is_active = True

    db.commit()
    return StatusResponse(
        success=True,
        message=f"Da mo lai {len(matching_edges)} canh giua {edge.source_id} va {edge.target_id}",
    )


@router.get("/banned/stations")
def list_banned_stations(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Station).filter(Station.is_active == False).all()


@router.get("/banned/lines")
def list_banned_lines(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Line).filter(Line.is_active == False).all()


@router.get("/banned/edges")
def list_banned_edges(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Edge).filter(Edge.is_active == False).all()
