from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.pathfinding import PathRequest, PathResponse
from app.service.pathfinding_service import find_path

router = APIRouter()


@router.post("/find", response_model=PathResponse)
def find_route(
    req: PathRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Nhận 2 toạ độ lat/lon từ bản đồ + priority.
    Tự động tìm ga tàu gần nhất rồi chạy Dijkstra.
    """
    try:
        return find_path(
            db=db,
            origin_lat=req.origin_lat,
            origin_lon=req.origin_lon,
            dest_lat=req.dest_lat,
            dest_lon=req.dest_lon,
            priority=req.priority,
            user_type=req.user_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Bắt các lỗi hệ thống không lường trước
        print(f"Lỗi hệ thống: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
"""
    Trả về
    origin_station:      str   # ga gần điểm xuất phát nhất
    dest_station:        str   # ga gần điểm đích nhất
    steps:               List[StepOut]
    total_distance_km:   float
    total_cost_yen:      int
    total_transfers:     int
    priority_used:       Priority
    user_type:           UserType
    """