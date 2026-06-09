from sqlalchemy import Column, String, Float, Integer, Boolean
from app.core.database import Base

class Line(Base):
    __tablename__ = "line"

    line_id   = Column(String(10),  primary_key=True)
    line_name = Column(String(100), nullable=False)
    color     = Column(String)
    # Thêm cột admin ban tuyến (không có trong DB gốc, thêm vào)
    is_active = Column(Boolean, default=True)


class Station(Base):
    __tablename__ = "stations"

    station_id   = Column(String(20), primary_key=True)
    station_name = Column(String(100), nullable=False)
    line_id      = Column(String(10))
    lat          = Column(Float)
    lon          = Column(Float)
    # Thêm cột admin ban ga
    is_active    = Column(Boolean, default=True)


class Edge(Base):
    __tablename__ = "edges"

    edge_id     = Column(Integer, primary_key=True, autoincrement=True)
    source_id   = Column(String(20))          # station_id ga đầu
    target_id   = Column(String(20))          # station_id ga cuối
    distance_km = Column(Float)
    fare_yen    = Column(Integer, default=0)  # Giá vé người lớn (yen)
    is_transfer = Column(Boolean, default=False)  # True = đây là cạnh đổi tàu
    is_active   = Column(Boolean, default=True)   # False = admin đã cấm đoạn này
