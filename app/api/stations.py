from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.subway import Station, Line, Edge
from app.service.pathfinding_service import find_nearest_station

router = APIRouter()

@router.get("/", response_model=List[dict])
def get_all_stations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lấy danh sách tất cả các ga đang hoạt động."""
    active_line_ids = {
        line.line_id
        for line in db.query(Line).filter(Line.is_active == True).all()
    }
    stations = (
        db.query(Station)
        .filter(Station.is_active == True)
        .filter(Station.line_id.in_(active_line_ids))
        .all()
    )
    return [
        {
            "station_id": s.station_id,
            "station_name": s.station_name,
            "line_id": s.line_id,
            "lat": s.lat,
            "lon": s.lon
        } for s in stations
    ]

@router.get("/lines", response_model=List[dict])
def get_all_lines(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lấy danh sách tất cả các tuyến tàu."""
    lines = db.query(Line).all()
    return [
        {
            "line_id": l.line_id,
            "line_name": l.line_name,
            "color": l.color,
            "is_active": l.is_active
        } for l in lines
    ]

@router.get("/edges", response_model=List[dict])
def get_all_edges(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lấy danh sách các đoạn đường (edges) đang hoạt động."""
    active_line_ids = {
        line.line_id
        for line in db.query(Line).filter(Line.is_active == True).all()
    }
    active_station_ids = {
        station.station_id
        for station in (
            db.query(Station)
            .filter(Station.is_active == True)
            .filter(Station.line_id.in_(active_line_ids))
            .all()
        )
    }
    edges = db.query(Edge).filter(Edge.is_active == True).all()
    return [
        {
            "edge_id": e.edge_id,
            "source_id": e.source_id,
            "target_id": e.target_id,
            "distance_km": e.distance_km,
            "fare_yen": e.fare_yen,
            "is_transfer": e.is_transfer
        } for e in edges
        if e.source_id in active_station_ids and e.target_id in active_station_ids
    ]

@router.get("/nearest")
def get_nearest_station(
    lat: float = Query(...), 
    lon: float = Query(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Tìm ga gần nhất dựa trên tọa độ lat/lon."""
    station = find_nearest_station(db, lat, lon)
    if not station:
        raise HTTPException(status_code=404, detail="Không tìm thấy ga nào")
    return {
        "station_id": station.station_id,
        "station_name": station.station_name,
        "distance_approx": "Calculated via Haversine"
    }
