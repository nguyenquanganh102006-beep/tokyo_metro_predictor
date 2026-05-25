import heapq
import math
from typing import List, Optional, Tuple, Dict
from sqlalchemy.orm import Session

from app.models.subway import Station, Edge, Line
from app.schemas.pathfinding import Priority, StepOut, PathResponse, UserType


# ─────────────────────────────────────────────
# 0. Tính tiền vé theo quãng đường
# ─────────────────────────────────────────────
def _calculate_fare(distance_km: float, user_type: UserType) -> int:
    """
    Tính tiền vé theo quãng đường và loại hành khách.
    Bảng giá dựa trên Tokyo Metro Regular Ticket Fares.
    """
    # Bảng giá vé người lớn (yen)
    if distance_km <= 6:
        adult_fare = 180
    elif distance_km <= 11:
        adult_fare = 210
    elif distance_km <= 19:
        adult_fare = 260
    elif distance_km <= 27:
        adult_fare = 300
    else:  # 28-40km
        adult_fare = 330
    
    # Vé trẻ em = 50% vé người lớn
    if user_type == UserType.child:
        return adult_fare // 2
    return adult_fare


# ─────────────────────────────────────────────
# 1. Tìm ga gần nhất với toạ độ lat/lon
# ─────────────────────────────────────────────
def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Khoảng cách (km) giữa 2 toạ độ theo công thức Haversine."""
    R = 6371
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def find_nearest_station(db: Session, lat: float, lon: float) -> Optional[Station]:
    """Trả về ga còn hoạt động gần toạ độ nhất."""
    stations = db.query(Station).filter(Station.is_active == True).all()
    if not stations:
        return None
    return min(stations, key=lambda s: _haversine(lat, lon, s.lat, s.lon))


# ─────────────────────────────────────────────
# 2. Xây đồ thị từ DB (chỉ cạnh còn active)
# ─────────────────────────────────────────────
def _build_graph(db: Session, priority: Priority) -> Dict[str, List[Tuple]]:
    """
    graph[node] = [(weight, neighbor, edge_obj), ...]
    weight tuỳ theo priority.
    """
    edges = (
        db.query(Edge)
        .filter(Edge.is_active == True)
        .all()
    )

    # Loại bỏ các cạnh có ga bị ban
    active_station_ids = {
        s.station_id
        for s in db.query(Station).filter(Station.is_active == True).all()
    }

    graph: Dict[str, List] = {}

    for e in edges:
        if e.source_id not in active_station_ids:
            continue
        if e.target_id not in active_station_ids:
            continue

        if priority == Priority.distance:
            w = e.distance_km +(1 if e.is_transfer else 0)
        else:  # transfers — đổi tàu tính thêm penalty cao
            penalty = 1000
            w = e.distance_km + (penalty if e.is_transfer else 0)

        graph.setdefault(e.source_id, []).append((w, e.target_id, e))
        graph.setdefault(e.target_id, []).append((w, e.source_id, e))  # đồ thị vô hướng

    return graph


# ─────────────────────────────────────────────
# 3. A* Algorithm
# ─────────────────────────────────────────────
def _a_star(graph: Dict, start: str, end: str, station_map: Dict):
    """
    A* pathfinding algorithm với heuristic là khoảng cách Haversine.
    Trả về (dist, prev_edge) để reconstruct path.
    dist[node] = chi phí nhỏ nhất từ start đến node.
    prev_edge[node] = (parent_node, edge_obj) để truy ngược.
    """
    # Heuristic: khoảng cách Haversine từ node đến end
    def heuristic(node: str) -> float:
        if node == end:
            return 0
        station_node = station_map.get(node)
        station_end = station_map.get(end)
        if station_node and station_end:
            return _haversine(station_node.lat, station_node.lon, 
                            station_end.lat, station_end.lon)  # Scale to match edge weights
        return 0
    
    dist: Dict[str, float] = {start: 0}
    prev_edge: Dict[str, Optional[Tuple]] = {start: None}
    # heap: (f_score, start) where f_score = g_score + h_score
    heap = [(heuristic(start), start)]
    visited = set()

    while heap:
        _, u = heapq.heappop(heap)
        
        if u in visited:
            continue
        visited.add(u)
        
        if u == end:
            break
            
        for w, v, edge in graph.get(u, []):
            if v in visited:
                continue
                
            nd = dist[u] + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev_edge[v] = (u, edge)
                f_score = nd + heuristic(v)
                heapq.heappush(heap, (f_score, v))

    return dist, prev_edge


def _reconstruct_path(prev_edge: Dict, end: str) -> List[Edge]:
    """Truy ngược từ end về start, trả về list Edge theo thứ tự đi."""
    path = []
    node = end
    while prev_edge.get(node) is not None:
        parent, edge = prev_edge[node]
        if parent != node:
            path.append((parent, node, edge))
        node = parent
    path.reverse()
    return path


# ─────────────────────────────────────────────
# 4. Main service function
# ─────────────────────────────────────────────
def find_path(
    db: Session,
    origin_lat: float, origin_lon: float,
    dest_lat:   float, dest_lon:   float,
    priority:   Priority,
    user_type:  UserType = UserType.adult,
) -> PathResponse:
    # Tìm ga gần nhất
    origin_station = find_nearest_station(db, origin_lat, origin_lon)
    dest_station   = find_nearest_station(db, dest_lat,   dest_lon)

    if origin_station is None or dest_station is None:
        raise ValueError("Không tìm thấy ga nào còn hoạt động")

    if origin_station.station_id == dest_station.station_id:
        raise ValueError("Điểm xuất phát và điểm đích cùng một ga")

    # Xây đồ thị & chạy A*
    graph = _build_graph(db, priority)
    
    # Lấy map station_id -> Station để tính heuristic
    station_map = {s.station_id: s for s in db.query(Station).all()}
    
    dist, prev_edge = _a_star(graph, origin_station.station_id, dest_station.station_id, station_map)

    if dest_station.station_id not in dist:
        raise ValueError("Không tìm được đường đi (có thể do các ga/đoạn đường bị cấm)")

    path_edges = _reconstruct_path(prev_edge, dest_station.station_id)

    for i, (_, tgt_id, _) in enumerate(path_edges):
        reached_station = station_map.get(tgt_id)
        if reached_station and reached_station.station_name == dest_station.station_name:
            path_edges = path_edges[:i + 1]
            dest_station = reached_station
            break

    # Lấy map line_id -> Line để lấy tên tuyến
    line_map = {l.line_id: l for l in db.query(Line).all()}

    steps: List[StepOut] = []
    total_distance = total_cost = total_transfers = 0
    line_distances = {}
    current_line = None
    
    for (src_id, tgt_id, edge) in path_edges:
        src_station = station_map.get(src_id)
        tgt_station = station_map.get(tgt_id)   
        if src_id == tgt_id:
            continue
        
        if src_id != tgt_id:
            line = line_map.get(src_station.line_id, None) if src_station else None
            distance = edge.distance_km or 0
        
            if line not in line_distances:
                line_distances[line] = 0
            line_distances[line] = line_distances.get(line, 0) + distance
            
            steps.append(StepOut(
                from_station = src_station.station_name if src_station else src_id,
                to_station   = tgt_station.station_name if tgt_station else tgt_id,
                line_name    = line.line_name if line else "Unknown",
                line_color   = line.color if line and line.color else "#000000",
                ###
                from_lat     = src_station.lat if src_station else 0.0,
                from_lon     = src_station.lon if src_station else 0.0,
                to_lat       = tgt_station.lat if tgt_station else 0.0,
                to_lon       = tgt_station.lon if tgt_station else 0.0,
                
                distance_km  = distance,
                is_transfer  = edge.is_transfer or False,
            ))
        
        distance_km = edge.distance_km or 0
        total_distance += distance_km
        if edge.is_transfer:
            total_transfers += 1
    total_cost = 0
    for lid, dist in line_distances.items():
        total_cost += _calculate_fare(dist, user_type)
    return PathResponse(
        origin_station    = origin_station.station_name,
        dest_station      = dest_station.station_name,
        steps             = steps,
        total_distance_km = round(total_distance, 3),
        total_cost_yen    = total_cost,
        total_transfers   = total_transfers,
        priority_used     = priority,
        user_type         = user_type,
    )
