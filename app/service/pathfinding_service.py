import heapq
import math
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.subway import Edge, Line, Station
from app.schemas.pathfinding import PathResponse, Priority, StepOut, UserType


TRANSFER_PENALTY = 1000.0
NEAREST_CANDIDATE_LIMIT = 4
ACCESS_DISTANCE_WEIGHT = 15.0
MAX_REASONABLE_ACCESS_KM = 1.2


def _calculate_fare(distance_km: float, user_type: UserType) -> int:
    if distance_km <= 6:
        adult_fare = 180
    elif distance_km <= 11:
        adult_fare = 210
    elif distance_km <= 19:
        adult_fare = 260
    elif distance_km <= 27:
        adult_fare = 300
    else:
        adult_fare = 330

    if user_type == UserType.child:
        return adult_fare // 2
    return adult_fare


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def _edge_distance(edge: Edge) -> float:
    return float(edge.distance_km or 0)


def _edge_weight(edge: Edge, priority: Priority) -> float:
    distance = _edge_distance(edge)
    if priority == Priority.distance:
        return distance+(2 if edge.is_transfer else 0)
    return distance + (TRANSFER_PENALTY if edge.is_transfer else 0)


def find_nearest_stations(db: Session, lat: float, lon: float, limit: int = NEAREST_CANDIDATE_LIMIT) -> List[Tuple[Station, float]]:
    active_line_ids = {
        line.line_id
        for line in db.query(Line).filter(Line.is_active == True).all()
    }
    if not active_line_ids:
        return []

    stations = (
        db.query(Station)
        .filter(Station.is_active == True)
        .filter(Station.line_id.in_(active_line_ids))
        .all()
    )
    if not stations:
        return []

    ranked = [
        (station, _haversine(lat, lon, station.lat, station.lon))
        for station in stations
    ]
    ranked.sort(key=lambda item: item[1])
    return ranked[:limit]


def find_nearest_station(db: Session, lat: float, lon: float) -> Optional[Station]:
    nearest = find_nearest_stations(db, lat, lon, limit=1)
    return nearest[0][0] if nearest else None


def _build_graph(db: Session, priority: Priority) -> Dict[str, List[Tuple[float, str, Edge]]]:
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

    graph: Dict[str, List[Tuple[float, str, Edge]]] = {}
    blocked_pairs = {
        frozenset((edge.source_id, edge.target_id))
        for edge in db.query(Edge).filter(Edge.is_active == False).all()
    }
    edges = db.query(Edge).filter(Edge.is_active == True).all()

    for edge in edges:
        if edge.source_id not in active_station_ids:
            continue
        if edge.target_id not in active_station_ids:
            continue
        if frozenset((edge.source_id, edge.target_id)) in blocked_pairs:
            continue

        weight = _edge_weight(edge, priority)
        graph.setdefault(edge.source_id, []).append((weight, edge.target_id, edge))
        graph.setdefault(edge.target_id, []).append((weight, edge.source_id, edge))

    return graph


def _a_star(
    graph: Dict[str, List[Tuple[float, str, Edge]]],
    start: str,
    end: str,
    station_map: Dict[str, Station],
    priority: Priority,
):
    def heuristic(node: str) -> float:
        current_station = station_map.get(node)
        end_station = station_map.get(end)
        if not current_station or not end_station:
            return 0.0
        return _haversine(
            current_station.lat,
            current_station.lon,
            end_station.lat,
            end_station.lon,
        )

    dist: Dict[str, float] = {start: 0.0}
    prev_edge: Dict[str, Optional[Tuple[str, Edge]]] = {start: None}
    heap = [(heuristic(start), start)]
    visited = set()

    while heap:
        _, current = heapq.heappop(heap)

        if current in visited:
            continue
        visited.add(current)

        if current == end:
            break

        for weight, neighbor, edge in graph.get(current, []):
            if neighbor in visited:
                continue

            new_dist = dist[current] + weight
            if new_dist < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_dist
                prev_edge[neighbor] = (current, edge)
                heapq.heappush(heap, (new_dist + heuristic(neighbor), neighbor))

    return dist, prev_edge


def _reconstruct_path(prev_edge: Dict[str, Optional[Tuple[str, Edge]]], end: str):
    path = []
    node = end

    while prev_edge.get(node) is not None:
        parent, edge = prev_edge[node]
        path.append((parent, node, edge))
        node = parent

    path.reverse()
    return path


def _route_fare(path_edges, station_map: Dict[str, Station], user_type: UserType) -> int:
    total = 0
    current_line_id = None
    current_distance = 0.0

    for src_id, _, edge in path_edges:
        src_station = station_map.get(src_id)
        line_id = src_station.line_id if src_station else None
        distance = _edge_distance(edge)

        if current_line_id is None:
            current_line_id = line_id

        if line_id != current_line_id:
            total += _calculate_fare(current_distance, user_type)
            current_line_id = line_id
            current_distance = 0.0

        current_distance += distance

    if current_distance > 0:
        total += _calculate_fare(current_distance, user_type)

    return total


def find_path(
    db: Session,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    priority: Priority,
    user_type: UserType = UserType.adult,
) -> PathResponse:
    origin_candidates = find_nearest_stations(db, origin_lat, origin_lon)
    dest_candidates = find_nearest_stations(db, dest_lat, dest_lon)

    if not origin_candidates or not dest_candidates:
        raise ValueError("Khong tim thay ga nao con hoat dong")

    graph = _build_graph(db, priority)
    station_map = {
        station.station_id: station
        for station in db.query(Station).filter(Station.is_active == True).all()
    }
    line_map = {
        line.line_id: line
        for line in db.query(Line).filter(Line.is_active == True).all()
    }

    best_route = None
    for origin_station, origin_access_km in origin_candidates:
        for dest_station, dest_access_km in dest_candidates:
            if origin_station.station_id == dest_station.station_id:
                continue
            if origin_access_km > MAX_REASONABLE_ACCESS_KM:
                continue
            if dest_access_km > MAX_REASONABLE_ACCESS_KM:
                continue

            dist, prev_edge = _a_star(
                graph,
                origin_station.station_id,
                dest_station.station_id,
                station_map,
                priority,
            )
            route_cost = dist.get(dest_station.station_id)
            if route_cost is None:
                continue

            # Penalize the access distance from clicked point to selected stations.
            # Walking to a station should matter more than the same distance by train.
            access_cost = (origin_access_km + dest_access_km) * ACCESS_DISTANCE_WEIGHT
            candidate_score = route_cost + access_cost
            path_edges = _reconstruct_path(prev_edge, dest_station.station_id)
            candidate = (
                candidate_score,
                access_cost,
                route_cost,
                origin_station,
                dest_station,
                path_edges,
            )
            if best_route is None or candidate[:3] < best_route[:3]:
                best_route = candidate

    if best_route is None:
        for origin_station, origin_access_km in origin_candidates:
            for dest_station, dest_access_km in dest_candidates:
                if origin_station.station_id == dest_station.station_id:
                    continue

                dist, prev_edge = _a_star(
                    graph,
                    origin_station.station_id,
                    dest_station.station_id,
                    station_map,
                    priority,
                )
                route_cost = dist.get(dest_station.station_id)
                if route_cost is None:
                    continue

                access_cost = (origin_access_km + dest_access_km) * ACCESS_DISTANCE_WEIGHT
                path_edges = _reconstruct_path(prev_edge, dest_station.station_id)
                candidate = (
                    route_cost + access_cost,
                    access_cost,
                    route_cost,
                    origin_station,
                    dest_station,
                    path_edges,
                )
                if best_route is None or candidate[:3] < best_route[:3]:
                    best_route = candidate

    if best_route is None:
        raise ValueError("Khong tim duoc duong di, co the do ga hoac canh bi chan")

    _, _, _, origin_station, dest_station, path_edges = best_route

    steps: List[StepOut] = []
    total_distance = 0.0
    total_transfers = 0

    for src_id, tgt_id, edge in path_edges:
        src_station = station_map.get(src_id)
        tgt_station = station_map.get(tgt_id)
        line = line_map.get(src_station.line_id) if src_station else None
        distance = _edge_distance(edge)

        steps.append(
            StepOut(
                from_station=src_station.station_name if src_station else src_id,
                to_station=tgt_station.station_name if tgt_station else tgt_id,
                line_name=line.line_name if line else "Unknown",
                line_color=line.color if line and line.color else "#000000",
                distance_km=distance,
                is_transfer=bool(edge.is_transfer),
                from_lat=src_station.lat if src_station else 0.0,
                from_lon=src_station.lon if src_station else 0.0,
                to_lat=tgt_station.lat if tgt_station else 0.0,
                to_lon=tgt_station.lon if tgt_station else 0.0,
            )
        )

        total_distance += distance
        if edge.is_transfer:
            total_transfers += 1

    return PathResponse(
        origin_station=origin_station.station_name,
        dest_station=dest_station.station_name,
        steps=steps,
        total_distance_km=round(total_distance, 3),
        total_cost_yen=_route_fare(path_edges, station_map, user_type),
        total_transfers=total_transfers,
        priority_used=priority,
        user_type=user_type,
    )
