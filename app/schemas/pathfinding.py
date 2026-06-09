from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class Priority(str, Enum):
    transfers = "transfers"  # tối thiểu số lần đổi tàu
    distance  = "distance"   # tối thiểu khoảng cách

class UserType(str, Enum):
    adult = "adult"
    child = "child"

class PathRequest(BaseModel):
    # Người dùng chọn 2 điểm lat/lon trên bản đồ
    origin_lat:  float
    origin_lon:  float
    dest_lat:    float
    dest_lon:    float
    priority:    Priority = Priority.distance
    user_type:   UserType = UserType.adult

class StepOut(BaseModel):
    from_station:   str
    to_station:     str
    line_name:      str
    line_color:     str
    distance_km:    float
    is_transfer:    bool
    #####
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float

class PathResponse(BaseModel):
    origin_station:      str   # ga gần điểm xuất phát nhất
    dest_station:        str   # ga gần điểm đích nhất
    steps:               List[StepOut]
    total_distance_km:   float
    total_cost_yen:      int
    total_transfers:     int
    priority_used:       Priority
    user_type:           UserType