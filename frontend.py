import streamlit as st
import requests
import folium
import math
from streamlit_folium import st_folium

# --- CẤU HÌNH HỆ THỐNG ---
API_BASE = "http://127.0.0.1:8000/api"
st.set_page_config(page_title="Tokyo Subway Pathfinder", layout="wide", page_icon="🚇")
st.markdown(
    """
    <style>
    html, body, .stApp, input, textarea, select, button {
        font-family: "Inter", "Segoe UI", "Roboto", "Arial", sans-serif;
    }
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] {
        font-family: "Inter", "Segoe UI", "Roboto", "Arial", sans-serif;
    }
    [data-testid="stIconMaterial"],
    .material-icons, .material-symbols-rounded, .material-symbols-outlined,
    [class*="material-icons"], [class*="material-symbols"] {
        font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

JAPAN_BOUNDS = {
    "min_lat": 20.0,
    "max_lat": 46.5,
    "min_lon": 122.0,
    "max_lon": 154.0,
}

# Khởi tạo Session State để lưu dữ liệu khi reload trang
if "token" not in st.session_state: st.session_state.token = None
if "role" not in st.session_state: st.session_state.role = "user"
if "origin" not in st.session_state: st.session_state.origin = [35.6812, 139.7671]
if "dest" not in st.session_state: st.session_state.dest = [35.6586, 139.7454]
if "path_data" not in st.session_state: st.session_state.path_data = None
if "map_lang" not in st.session_state: st.session_state.map_lang = "en"
if "banned_station_visible_count" not in st.session_state: st.session_state.banned_station_visible_count = 5
if "banned_edge_visible_count" not in st.session_state: st.session_state.banned_edge_visible_count = 5
if "show_network" not in st.session_state: st.session_state.show_network = False
if "show_current_route" not in st.session_state: st.session_state.show_current_route = True
if "selected_network_line_id" not in st.session_state: st.session_state.selected_network_line_id = None
if "selected_network_edge_id" not in st.session_state: st.session_state.selected_network_edge_id = None
if "map_perf_defaults_applied" not in st.session_state:
    st.session_state.show_network = False
    st.session_state.show_station_dots = False
    st.session_state.map_perf_defaults_applied = True

def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

stations_list = []
map_edges_list = []
map_lines_list = []

@st.cache_data(ttl=60, show_spinner=False)
def fetch_api_json(endpoint, token):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=15)
    if response.status_code != 200:
        return []
    return response.json()

def clear_map_cache():
    fetch_api_json.clear()

def invalidate_route_cache():
    st.session_state.path_data = None
    st.session_state.selected_network_line_id = None
    st.session_state.selected_network_edge_id = None

def geocode_place(place_query):
    """Đổi tên địa điểm/địa chỉ sang toạ độ lat/lon bằng Nominatim."""
    if not place_query or not place_query.strip():
        return None

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place_query.strip(), "format": "json", "limit": 1},
            headers={"User-Agent": "tokyo-subway-pathfinder/1.0"},
            timeout=10,
        )
        if response.status_code != 200:
            return None

        items = response.json()
        if not items:
            return None

        top = items[0]
        return {
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
            "display_name": top.get("display_name", place_query.strip()),
        }
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return None

def edge_line_id(edge, station_by_id):
    source = station_by_id.get(edge.get("source_id"))
    target = station_by_id.get(edge.get("target_id"))
    if not source or not target:
        return None
    if source.get("line_id") != target.get("line_id"):
        return None
    return source.get("line_id")

def normalize_line_group_name(line_name):
    if not line_name:
        return None
    line_name = str(line_name).strip()
    suffixes = (" Branch Line", " branch line")
    for suffix in suffixes:
        if line_name.endswith(suffix):
            return line_name[: -len(suffix)].strip()
    return line_name

def line_group_key(line_id, line_by_id):
    line = line_by_id.get(line_id)
    if not line:
        return line_id
    return normalize_line_group_name(line.get("line_name")) or line_id

def edge_group_key(edge, station_by_id, line_by_id):
    source = station_by_id.get(edge.get("source_id"))
    target = station_by_id.get(edge.get("target_id"))
    if not source or not target:
        return None

    source_group = line_group_key(source.get("line_id"), line_by_id)
    target_group = line_group_key(target.get("line_id"), line_by_id)
    if source_group == target_group:
        return source_group
    return None

def point_segment_distance_km(point_lat, point_lon, source, target):
    lat_scale = 111.32
    lon_scale = 111.32 * math.cos(math.radians(point_lat))

    px = point_lon * lon_scale
    py = point_lat * lat_scale
    ax = float(source.get("lon")) * lon_scale
    ay = float(source.get("lat")) * lat_scale
    bx = float(target.get("lon")) * lon_scale
    by = float(target.get("lat")) * lat_scale

    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ab_len_sq))
    cx = ax + t * abx
    cy = ay + t * aby
    return math.hypot(px - cx, py - cy)

def find_nearest_edge(point_lat, point_lon, stations, edges, lines=None):
    station_by_id = {station.get("station_id"): station for station in stations}
    line_by_id = {line.get("line_id"): line for line in (lines or [])}
    best = None
    best_distance = float("inf")

    for edge in edges:
        source = station_by_id.get(edge.get("source_id"))
        target = station_by_id.get(edge.get("target_id"))
        if not source or not target:
            continue
        if edge.get("is_transfer") and not edge_group_key(edge, station_by_id, line_by_id):
            continue
        if source.get("line_id") != target.get("line_id") and not edge_group_key(edge, station_by_id, line_by_id):
            continue

        distance = point_segment_distance_km(point_lat, point_lon, source, target)
        if distance < best_distance:
            best = edge
            best_distance = distance

    if not best:
        return None, None
    selected_line_id = edge_line_id(best, station_by_id)
    if selected_line_id is None:
        source = station_by_id.get(best.get("source_id"))
        selected_line_id = source.get("line_id") if source else None
    return best, selected_line_id

def draw_network(m, stations, edges, lines, selected_line_id=None, selected_edge_id=None, show_station_dots=False):
    """Ve lop nen gom tat ca ga va canh, de mo de tuyen tim duoc noi bat hon."""
    if not stations:
        return m

    station_by_id = {station.get("station_id"): station for station in stations}
    line_color_by_id = {
        line.get("line_id"): line.get("color") or "#6B7280"
        for line in lines
    }
    line_by_id = {line.get("line_id"): line for line in lines}
    selected_line_group = line_group_key(selected_line_id, line_by_id) if selected_line_id else None

    network_layer = folium.FeatureGroup(name="Mạng lưới metro", show=True)

    for edge in edges:
        source = station_by_id.get(edge.get("source_id"))
        target = station_by_id.get(edge.get("target_id"))
        if not source or not target:
            continue

        line_id = edge_line_id(edge, station_by_id)
        edge_line_group = line_group_key(line_id, line_by_id) if line_id else edge_group_key(edge, station_by_id, line_by_id)
        is_selected_line = selected_line_group and edge_line_group == selected_line_group
        is_selected_edge = selected_edge_id and edge.get("edge_id") == selected_edge_id
        is_transfer = edge.get("is_transfer") or line_id is None
        is_same_group_connector = is_transfer and edge_line_group is not None
        if selected_line_id and not is_selected_line and not is_selected_edge:
            continue
        if is_transfer and not is_selected_edge:
            if not is_selected_line and not is_same_group_connector:
                continue

        color = line_color_by_id.get(line_id or selected_line_id, "#6B7280")
        if is_same_group_connector and line_id is None:
            source = station_by_id.get(edge.get("source_id"))
            color = line_color_by_id.get(source.get("line_id") if source else None, color)
        if is_selected_edge:
            weight = 7
            opacity = 0.92
        elif is_selected_line and not is_transfer:
            weight = 5
            opacity = 0.92
        elif is_selected_line and is_transfer:
            weight = 3.5
            opacity = 0.65
        else:
            weight = 1.2
            opacity = 0.18
        line_kwargs = {
            "locations": [
                [source.get("lat"), source.get("lon")],
                [target.get("lat"), target.get("lon")],
            ],
            "color": color,
            "weight": weight,
            "opacity": opacity,
        }
        if is_selected_line:
            line_kwargs["tooltip"] = f"{source.get('station_name')} -> {target.get('station_name')}"
        folium.PolyLine(**line_kwargs).add_to(network_layer)

    if not show_station_dots and not selected_line_id:
        network_layer.add_to(m)
        return m

    for station in stations:
        line_id = station.get("line_id")
        station_line_group = line_group_key(line_id, line_by_id) if line_id else None
        is_selected_line = selected_line_group and station_line_group == selected_line_group
        color = line_color_by_id.get(line_id, "#2563EB")
        folium.CircleMarker(
            location=[station.get("lat"), station.get("lon")],
            radius=4.2 if is_selected_line else 2.0,
            color="#111827",
            weight=0.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.9 if is_selected_line else (0.18 if selected_line_id else 0.85),
            tooltip=f"{station.get('station_name')} (ID: {station.get('station_id')})",
        ).add_to(network_layer)

    network_layer.add_to(m)
    return m

def draw_routes(m, lang):
    """Vẽ routes trên bản đồ"""
    if not st.session_state.show_current_route:
        return m

    if st.session_state.path_data:
        steps = st.session_state.path_data.get('steps', [])
        for stp in steps:
            if all(k in stp for k in ('from_lat', 'from_lon', 'to_lat', 'to_lon')):
                p1 = [stp['from_lat'], stp['from_lon']]
                p2 = [stp['to_lat'], stp['to_lon']]
                line_color = stp.get('line_color', '#2E86C1')
                
                folium.PolyLine(
                    locations=[p1, p2],
                    color=line_color, weight=6, opacity=0.8,
                    dash_array="8, 8" if stp.get('is_transfer') else None,
                    tooltip=f"{stp.get('line_name', 'Tàu điện')} ({stp.get('distance_km')} km)"
                ).add_to(m)
                
                folium.CircleMarker(p1, radius=4, color="white", fill=True, fill_color=line_color).add_to(m)
                folium.CircleMarker(p2, radius=4, color="white", fill=True, fill_color=line_color).add_to(m)
    
    folium.Marker(st.session_state.origin, icon=folium.Icon(color='green', icon='play'), tooltip="Điểm đi").add_to(m)
    folium.Marker(st.session_state.dest, icon=folium.Icon(color='red', icon='stop'), tooltip="Điểm đến").add_to(m)
    return m

def create_map(lang, stations=None, edges=None, lines=None, show_network=True, selected_line_id=None, selected_edge_id=None, show_station_dots=False):
    """Tạo bản đồ (lang: 'ja' hoặc 'en')"""
    map_options = {
        "location": [35.6895, 139.6917],
        "zoom_start": 12,
        "min_zoom": 5,
        "max_bounds": True,
        **JAPAN_BOUNDS,
    }

    if lang == "en":
        m = folium.Map(**map_options, tiles='CartoDB positron')
    else:
        m = folium.Map(**map_options)  # OpenStreetMap - Tiếng Nhật
    if show_network:
        draw_network(
            m,
            stations or [],
            edges or [],
            lines or [],
            selected_line_id=selected_line_id,
            selected_edge_id=selected_edge_id,
            show_station_dots=show_station_dots,
        )

    return draw_routes(m, lang)

def group_steps_by_line(steps):
    """Nhóm các step theo line_name liên tiếp"""
    if not steps:
        return []

    groups = []
    current_group = [steps[0]]
    current_line = steps[0].get('line_name')

    for step in steps[1:]:
        if step.get('line_name') == current_line:
            # Cùng tuyến
            current_group.append(step)
        else:
            # Khác tuyến - bắt đầu nhóm mới
            groups.append(current_group)
            current_group = [step]
            current_line = step.get('line_name')

    groups.append(current_group)
    return groups

def calculate_route_fare(distance_km, user_type):
    """Tinh tien ve cho mot tuyen gom nhieu edge, giong logic backend."""
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

    if user_type == "child":
        return adult_fare // 2
    return adult_fare

def step_distance(step):
    try:
        return float(step.get('distance_km') or 0)
    except (TypeError, ValueError):
        return 0.0

def station_label(station):
    return f"{station.get('station_name')} (ID: {station.get('station_id')})"

def nearest_station_index(stations, point):
    if not stations:
        return 0

    def score(station):
        try:
            return (float(station.get('lat')) - point[0]) ** 2 + (float(station.get('lon')) - point[1]) ** 2
        except (TypeError, ValueError):
            return float("inf")

    return min(range(len(stations)), key=lambda idx: score(stations[idx]))

# --- LAYOUT CHÍNH: PANEL TRÁI (FORM) + PANEL PHẢI (MAP LỚN) ---
left_col, right_col = st.columns([1.0, 2.7], gap="large")

with left_col:
    st.write("### 🎛️ Điều khiển")

    if not st.session_state.token:
        auth_login_tab, auth_register_tab = st.tabs(["Đăng nhập", "Đăng ký"])

        with auth_login_tab:
            u = st.text_input("Username", key="login_username")
            p = st.text_input("Password", type="password", key="login_password")
            if st.button("Đăng nhập", use_container_width=True, key="btn_login"):
                if u and p:
                    res = requests.post(f"{API_BASE}/auth/login", data={"username": u, "password": p})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.role = data.get("role", "user")
                        st.success("✅ Đăng nhập thành công!")
                        st.rerun()
                    else:
                        st.error("❌ Sai tài khoản hoặc mật khẩu!")
                else:
                    st.warning("⚠️ Vui lòng nhập tài khoản và mật khẩu!")

        with auth_register_tab:
            new_username = st.text_input("Tên đăng nhập", key="register_username")
            new_password = st.text_input("Mật khẩu", type="password", key="register_password")
            confirm_password = st.text_input("Xác nhận mật khẩu", type="password", key="confirm_password")
            if st.button("Đăng ký", use_container_width=True, key="btn_register"):
                if not new_username or not new_password or not confirm_password:
                    st.warning("⚠️ Vui lòng điền đầy đủ thông tin!")
                elif new_password != confirm_password:
                    st.error("❌ Mật khẩu xác nhận không khớp!")
                elif len(new_password) < 6:
                    st.warning("⚠️ Mật khẩu phải có ít nhất 6 ký tự!")
                else:
                    res = requests.post(
                        f"{API_BASE}/auth/register",
                        json={"username": new_username, "password": new_password}
                    )
                    if res.status_code == 201:
                        st.success("✅ Đăng ký thành công! Vui lòng đăng nhập.")
                    elif res.status_code == 400:
                        st.error("❌ Tên đăng nhập đã tồn tại! Vui lòng chọn tên khác.")
                    else:
                        try:
                            error_msg = res.json().get("detail", "Lỗi không xác định")
                        except ValueError:
                            error_msg = res.text.strip() or f"HTTP {res.status_code}"
                        st.error(f"❌ Lỗi: {error_msg}")

        st.info("💡 Sau khi đăng nhập, bạn sẽ tìm đường ngay tại panel này.")
    else:
        top_left_col1, top_left_col2 = st.columns([3, 1])
        with top_left_col1:
            st.success(f"Đang đăng nhập: {st.session_state.role.upper()}")
        with top_left_col2:
            if st.button("Đăng xuất", use_container_width=True):
                st.session_state.token = None
                st.session_state.path_data = None
                st.rerun()

        btn_col, info_col = st.columns([0.5, 3])
        with btn_col:
            if st.button("🔄", use_container_width=True, help="Chuyển ngôn ngữ"):
                st.session_state.map_lang = "ja" if st.session_state.map_lang == "en" else "en"
                st.rerun()
        with info_col:
            lang_display = "🇬🇧 Tiếng Anh" if st.session_state.map_lang == "en" else "🇯🇵 Tiếng Nhật"
            st.write(f"#### ⚙️ Thông số lộ trình ({lang_display})")

        try:
            stations_list = fetch_api_json("/stations/", st.session_state.token)
        except:
            stations_list = []

        st.write("#### ✍️ Chọn ga đi / ga đến")
        current_map_mode = st.session_state.get("mode_select", "Điểm đi")
        needs_edges = (
            st.session_state.show_network
            or current_map_mode == "Chọn cạnh"
            or st.session_state.role == "admin"
        )
        needs_lines = (
            st.session_state.show_network
            or st.session_state.selected_network_line_id
            or st.session_state.role == "admin"
        )

        if needs_edges:
            try:
                map_edges_list = fetch_api_json("/stations/edges", st.session_state.token)
            except:
                map_edges_list = []

        if needs_lines:
            try:
                map_lines_list = fetch_api_json("/stations/lines", st.session_state.token)
            except:
                map_lines_list = []

        if st.session_state.role == "admin":
            st.checkbox("Hiện toàn bộ ga và đường tàu", key="show_network")
            st.checkbox("Hiện chấm ga trên bản đồ", value=False, key="show_station_dots")
            st.checkbox("Hiện đường đi và điểm đi/đến", key="show_current_route")
        else:
            st.session_state.show_network = False
            st.session_state.show_station_dots = False
            st.session_state.show_current_route = True
            st.session_state.selected_network_line_id = None
            st.session_state.selected_network_edge_id = None
        if st.session_state.selected_network_line_id:
            selected_line = next(
                (
                    line
                    for line in map_lines_list
                    if line.get("line_id") == st.session_state.selected_network_line_id
                ),
                None,
            )
            selected_line_name = selected_line.get("line_name") if selected_line else st.session_state.selected_network_line_id
            selected_group_name = normalize_line_group_name(selected_line_name) or selected_line_name
            st.caption(f"Đang làm nổi bật: {selected_group_name}")
            if st.button("Bỏ chọn tuyến đang nổi bật", use_container_width=True, key="clear_selected_network_line"):
                st.session_state.selected_network_line_id = None
                st.session_state.selected_network_edge_id = None
                st.rerun()

        in_col1, in_col2 = st.columns(2)
        if stations_list:
            station_options = [station_label(station) for station in stations_list]
            station_by_label = dict(zip(station_options, stations_list))

            with in_col1:
                origin_station_label = st.selectbox(
                    "Tìm và chọn ga đi",
                    options=station_options,
                    index=None,
                    placeholder="Gõ tên ga đi hoặc ID ga...",
                    key="origin_station_select",
                )
            with in_col2:
                dest_station_label = st.selectbox(
                    "Tìm và chọn ga đến",
                    options=station_options,
                    index=None,
                    placeholder="Gõ tên ga đến hoặc ID ga...",
                    key="dest_station_select",
                )

            if st.button("📌 Áp dụng ga đã chọn", use_container_width=True):
                if not origin_station_label or not dest_station_label:
                    st.warning("Vui lòng chọn đủ ga đi và ga đến.")
                else:
                    origin_station = station_by_label[origin_station_label]
                    dest_station = station_by_label[dest_station_label]
                    st.session_state.origin = [float(origin_station["lat"]), float(origin_station["lon"])]
                    st.session_state.dest = [float(dest_station["lat"]), float(dest_station["lon"])]
                    st.session_state.path_data = None
                    st.rerun()
        else:
            st.error("Không thể tải danh sách ga từ Database.")

        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.caption(f"🟢 {st.session_state.origin[0]:.4f}, {st.session_state.origin[1]:.4f}")
        with col_info2:
            st.caption(f"🔴 {st.session_state.dest[0]:.4f}, {st.session_state.dest[1]:.4f}")

        sel_col1, sel_col2 = st.columns(2)
        with sel_col1:
            prio = st.selectbox("Ưu tiên", ["distance", "transfers"], key="priority_select")
        with sel_col2:
            user = st.selectbox("Loại", ["adult", "child"], key="user_select")

        if st.button("🚀 TÌM", type="primary", use_container_width=True):
            payload = {
                "origin_lat": st.session_state.origin[0], "origin_lon": st.session_state.origin[1],
                "dest_lat": st.session_state.dest[0], "dest_lon": st.session_state.dest[1],
                "priority": prio, "user_type": user
            }
            res = requests.post(f"{API_BASE}/path/find", json=payload, headers=get_headers())
            if res.status_code == 200:
                st.session_state.path_data = res.json()
                st.rerun()
            else:
                try:
                    error_msg = res.json().get("detail", "Không tìm thấy đường đi!")
                except ValueError:
                    error_msg = res.text.strip() or f"HTTP {res.status_code}"
                st.error(f"❌ {error_msg}")

        if st.session_state.path_data:
            res = st.session_state.path_data
            st.success(f"📍 {res['total_distance_km']} km | 💰 {res['total_cost_yen']} ¥ | 🔄 {res['total_transfers']} đổi tàu")
            st.info(f"Ga gần điểm đi: {res['origin_station']} | Ga gần điểm đến: {res['dest_station']}")
            with st.expander("📄 Chi tiết các chặng"):
                line_groups = group_steps_by_line(res['steps'])
                fare_user_type = res.get('user_type', user)
                for i, group in enumerate(line_groups, 1):
                    first_step = group[0]
                    last_step = group[-1]

                    total_distance = sum(step_distance(s) for s in group)
                    total_fare = calculate_route_fare(total_distance, fare_user_type)
                    line_color = first_step.get('line_color', '#2E86C1')

                    with st.expander(f"🚇 **{first_step.get('line_name')}**: {first_step['from_station']} → {last_step['to_station']} | 📏 {total_distance:.1f} km | 💰 {total_fare} ¥"):
                        st.caption(f"Tuyến này gồm {len(group)} edge | Tổng tiền tuyến: {total_fare} ¥")
                        for j, step in enumerate(group, 1):
                            transfer_tag = " 🔀" if step.get('is_transfer') else ""
                            st.caption(f"  {j}. {step['from_station']} → {step['to_station']} | {step_distance(step):.3f} km{transfer_tag}")


        if st.session_state.role == "admin":
            with st.expander("🛠️ Quản trị (Admin)"):
                # --- Phần 1: Chọn ga để cấm/mở ---
                st.subheader("📍 Quản lý Ga")

                if stations_list:
                    s_map = {f"{s.get('station_name')} (ID: {s.get('station_id')})": s.get('station_id') for s in stations_list}
                    sel_s = st.selectbox(
                        "Tìm và chọn ga cần thao tác",
                        options=list(s_map.keys()),
                        index=None,
                        placeholder="Gõ tên ga hoặc ID ga...",
                        key="station_admin_select",
                    )
                    if sel_s:
                        col_btn1, col_btn2 = st.columns(2)
                        if col_btn1.button("🚫 Chặn ga này", use_container_width=True):
                            requests.post(f"{API_BASE}/admin/station/ban", json={"station_id": s_map[sel_s]}, headers=get_headers())
                            st.toast(f"Đã chặn ga {sel_s}")
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()
                        if col_btn2.button("✅ Mở ga này", use_container_width=True):
                            requests.post(f"{API_BASE}/admin/station/unban", json={"station_id": s_map[sel_s]}, headers=get_headers())
                            st.toast(f"Đã mở ga {sel_s}")
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()
                else:
                    st.error("Không thể tải danh sách ga từ Database.")

                # --- Phần 2: Danh sách các ga bị cấm ---
                st.write("#### 🔴 Danh sách các ga bị cấm")
                try:
                    banned_stations_res = requests.get(f"{API_BASE}/admin/banned/stations", headers=get_headers())
                    banned_stations = banned_stations_res.json() if banned_stations_res.status_code == 200 else []
                except:
                    banned_stations = []

                if banned_stations:
                    st.write(f"**Tổng cộng: {len(banned_stations)} ga bị cấm**")
                    visible_count = min(st.session_state.banned_station_visible_count, len(banned_stations))
                    visible_banned_stations = banned_stations[:visible_count]
                    select_all_stations = st.checkbox("☑️ Chọn tất cả các ga", key="select_all_banned_stations")
                    
                    selected_to_unban_stations = []
                    
                    if select_all_stations:
                        selected_to_unban_stations = [
                            {
                                'station_id': station.get('station_id'),
                                'station_name': station.get('station_name')
                            }
                            for station in banned_stations
                        ]
                        for station in visible_banned_stations:
                            st.caption(f"✅ 🚇 {station.get('station_name')} (ID: {station.get('station_id')})")
                    else:
                        for station in visible_banned_stations:
                            col_checkbox, col_name = st.columns([0.5, 3])
                            with col_checkbox:
                                is_checked = st.checkbox(
                                    label="",
                                    key=f"station_ban_{station.get('station_id')}",
                                    label_visibility="collapsed"
                                )
                                if is_checked:
                                    selected_to_unban_stations.append({
                                        'station_id': station.get('station_id'),
                                        'station_name': station.get('station_name')
                                    })
                            with col_name:
                                st.caption(f"🚇 {station.get('station_name')} (ID: {station.get('station_id')})")

                    more_col, collapse_col = st.columns(2)
                    if visible_count < len(banned_stations):
                        if more_col.button(
                            f"Xem thêm ({len(banned_stations) - visible_count} ga)",
                            use_container_width=True,
                            key="show_more_banned_stations",
                        ):
                            st.session_state.banned_station_visible_count = min(visible_count + 5, len(banned_stations))
                            st.rerun()
                    if visible_count > 5:
                        if collapse_col.button("Thu gọn", use_container_width=True, key="collapse_banned_stations"):
                            st.session_state.banned_station_visible_count = 5
                            st.rerun()
                     
                    if selected_to_unban_stations:
                        if st.button("✅ Mở các ga được chọn", use_container_width=True, key="unban_selected_stations"):
                            for station in selected_to_unban_stations:
                                requests.post(f"{API_BASE}/admin/station/unban", 
                                            json={"station_id": station['station_id']}, 
                                            headers=get_headers())
                            st.success(f"✅ Đã mở {len(selected_to_unban_stations)} ga!")
                            st.session_state.banned_station_visible_count = 5
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()
                else:
                    st.session_state.banned_station_visible_count = 5
                    st.info("✅ Không có ga nào bị cấm")

                st.divider()

                # --- Phần 3: Chọn tuyến để cấm/mở ---
                st.subheader("🚆 Quản lý Tuyến")
                try:
                    lines_res = requests.get(f"{API_BASE}/stations/lines", headers=get_headers())
                    lines_list = lines_res.json() if lines_res.status_code == 200 else []
                except:
                    lines_list = []

                if lines_list:
                    l_map = {f"{l.get('line_name')} (ID: {l.get('line_id')})": l.get('line_id') for l in lines_list}
                    sel_l = st.selectbox(
                        "Tìm và chọn tuyến cần thao tác",
                        options=list(l_map.keys()),
                        index=None,
                        placeholder="Gõ tên tuyến hoặc ID tuyến...",
                        key="line_select",
                    )
                    if sel_l:
                        col_btn3, col_btn4 = st.columns(2)
                        if col_btn3.button("🚫 Chặn tuyến này", use_container_width=True):
                            requests.post(f"{API_BASE}/admin/line/ban", json={"line_id": l_map[sel_l]}, headers=get_headers())
                            st.toast(f"Đã chặn tuyến {sel_l}")
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()
                        if col_btn4.button("✅ Mở tuyến này", use_container_width=True):
                            requests.post(f"{API_BASE}/admin/line/unban", json={"line_id": l_map[sel_l]}, headers=get_headers())
                            st.toast(f"Đã mở tuyến {sel_l}")
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()

                # --- Phần 4: Danh sách tuyến đã đóng ---
                st.write("#### 🔴 Danh sách tuyến đã đóng")
                try:
                    banned_lines_res = requests.get(f"{API_BASE}/admin/banned/lines", headers=get_headers())
                    banned_lines = banned_lines_res.json() if banned_lines_res.status_code == 200 else []
                except:
                    banned_lines = []

                if banned_lines:
                    st.write(f"**Tổng cộng: {len(banned_lines)} tuyến đã đóng**")
                    select_all_lines = st.checkbox("☑️ Chọn tất cả các tuyến", key="select_all_banned_lines")
                    
                    selected_to_unban_lines = []
                    
                    if select_all_lines:
                        selected_to_unban_lines = [
                            {
                                'line_id': line.get('line_id'),
                                'line_name': line.get('line_name')
                            }
                            for line in banned_lines
                        ]
                        for line in banned_lines:
                            st.caption(f"✅ 🚇 {line.get('line_name')} (ID: {line.get('line_id')})")
                    else:
                        for line in banned_lines:
                            col_checkbox, col_name = st.columns([0.5, 3])
                            with col_checkbox:
                                is_checked = st.checkbox(
                                    label="",
                                    key=f"line_ban_{line.get('line_id')}",
                                    label_visibility="collapsed"
                                )
                                if is_checked:
                                    selected_to_unban_lines.append({
                                        'line_id': line.get('line_id'),
                                        'line_name': line.get('line_name')
                                    })
                            with col_name:
                                st.caption(f"🚇 {line.get('line_name')} (ID: {line.get('line_id')})")
                    
                    if selected_to_unban_lines:
                        if st.button("✅ Mở các tuyến được chọn", use_container_width=True, key="unban_selected_lines"):
                            for line in selected_to_unban_lines:
                                requests.post(f"{API_BASE}/admin/line/unban", 
                                            json={"line_id": line['line_id']}, 
                                            headers=get_headers())
                            st.success(f"✅ Đã mở {len(selected_to_unban_lines)} tuyến!")
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()
                else:
                    st.info("✅ Không có tuyến nào bị đóng")

                st.divider()

                # --- Phan 5: Quan ly canh noi giua 2 ga ---
                st.subheader("Quản lý Cạnh nối giữa 2 ga")

                station_name_by_id = {
                    station.get("station_id"): station.get("station_name")
                    for station in stations_list
                }

                def format_edge(edge):
                    source_id = edge.get("source_id")
                    target_id = edge.get("target_id")
                    source_name = station_name_by_id.get(source_id, source_id)
                    target_name = station_name_by_id.get(target_id, target_id)
                    transfer_label = " | transfer" if edge.get("is_transfer") else ""
                    return (
                        f"ID {edge.get('edge_id')}: "
                        f"{source_name} ({source_id}) -> {target_name} ({target_id}) | "
                        f"{edge.get('distance_km')} km | {edge.get('fare_yen')} yen"
                        f"{transfer_label}"
                    )

                edges_list = map_edges_list

                if edges_list:
                    edge_options = {format_edge(edge): edge.get("edge_id") for edge in edges_list}
                    selected_edge_label = st.selectbox(
                        "Tìm và chọn cạnh đang hoạt động cần chặn",
                        options=list(edge_options.keys()),
                        index=None,
                        placeholder="Gõ ID cạnh, ga đầu hoặc ga cuối...",
                        key="edge_select",
                    )
                    if selected_edge_label:
                        if st.button("Chặn cạnh này", use_container_width=True, key="ban_selected_edge"):
                            selected_edge_id = edge_options[selected_edge_label]
                            edge_res = requests.post(
                                f"{API_BASE}/admin/edge/ban",
                                json={"edge_id": selected_edge_id},
                                headers=get_headers(),
                            )
                            if edge_res.status_code == 200:
                                st.toast(f"Đã chặn cạnh ID {selected_edge_id}")
                                clear_map_cache()
                                invalidate_route_cache()
                                st.rerun()
                            else:
                                st.error(f"Không thể chặn cạnh ID {selected_edge_id}")
                else:
                    st.info("Không có cạnh đang hoạt động để chặn.")

                st.write("#### Danh sách cạnh đã chặn")
                try:
                    banned_edges_res = requests.get(f"{API_BASE}/admin/banned/edges", headers=get_headers())
                    banned_edges = banned_edges_res.json() if banned_edges_res.status_code == 200 else []
                except:
                    banned_edges = []

                if banned_edges:
                    st.write(f"**ổng cộng: {len(banned_edges)} cạnh đã chặn**")
                    visible_edge_count = min(st.session_state.banned_edge_visible_count, len(banned_edges))
                    visible_banned_edges = banned_edges[:visible_edge_count]
                    select_all_edges = st.checkbox("Chọn tất cả các cạnh", key="select_all_banned_edges")

                    selected_to_unban_edges = []

                    if select_all_edges:
                        selected_to_unban_edges = banned_edges
                        for edge in visible_banned_edges:
                            st.caption(f"Đã chọn: {format_edge(edge)}")
                    else:
                        for edge in visible_banned_edges:
                            col_checkbox, col_name = st.columns([0.5, 3])
                            with col_checkbox:
                                is_checked = st.checkbox(
                                    label="",
                                    key=f"edge_ban_{edge.get('edge_id')}",
                                    label_visibility="collapsed",
                                )
                                if is_checked:
                                    selected_to_unban_edges.append(edge)
                            with col_name:
                                st.caption(format_edge(edge))

                    edge_more_col, edge_collapse_col = st.columns(2)
                    if visible_edge_count < len(banned_edges):
                        if edge_more_col.button(
                            f"Xem them ({len(banned_edges) - visible_edge_count} canh)",
                            use_container_width=True,
                            key="show_more_banned_edges",
                        ):
                            st.session_state.banned_edge_visible_count = min(visible_edge_count + 5, len(banned_edges))
                            st.rerun()
                    if visible_edge_count > 5:
                        if edge_collapse_col.button("Thu gọn", use_container_width=True, key="collapse_banned_edges"):
                            st.session_state.banned_edge_visible_count = 5
                            st.rerun()

                    if selected_to_unban_edges:
                        if st.button("Mở các cạnh được chọn", use_container_width=True, key="unban_selected_edges"):
                            success_count = 0
                            for edge in selected_to_unban_edges:
                                unban_res = requests.post(
                                    f"{API_BASE}/admin/edge/unban",
                                    json={"edge_id": edge.get("edge_id")},
                                    headers=get_headers(),
                                )
                                if unban_res.status_code == 200:
                                    success_count += 1
                            st.success(f"Đã mở {success_count} cạnh!")
                            st.session_state.banned_edge_visible_count = 5
                            clear_map_cache()
                            invalidate_route_cache()
                            st.rerun()
                else:
                    st.session_state.banned_edge_visible_count = 5
                    st.info("Không có cạnh nào đã chặn.")

with right_col:
    st.write("### Bản đồ")
    map_modes = ["Điểm đi", "Điểm đến"]
    if st.session_state.role == "admin":
        map_modes.append("Chọn cạnh")
    if st.session_state.get("mode_select") not in map_modes:
        st.session_state.mode_select = "Điểm đi"
    mode = st.radio(
        "Chọn thao tác trên bản đồ:",
        map_modes,
        horizontal=True,
        key="mode_select",
    )
    map_should_show_network = (
        st.session_state.show_network
        or mode == "Chọn cạnh"
        or bool(st.session_state.selected_network_line_id)
    )
    m = create_map(
        st.session_state.map_lang,
        stations=stations_list,
        edges=map_edges_list,
        lines=map_lines_list,
        show_network=map_should_show_network,
        selected_line_id=st.session_state.selected_network_line_id,
        selected_edge_id=st.session_state.selected_network_edge_id,
        show_station_dots=st.session_state.show_station_dots,
    )
    out = st_folium(m, width=None, height=820, key=f"map_{st.session_state.map_lang}", returned_objects=["last_clicked"])

    if out and out.get("last_clicked"):
        new_pos = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
        if mode == "Chọn cạnh":
            selected_edge, selected_line_id = find_nearest_edge(
                new_pos[0],
                new_pos[1],
                stations_list,
                map_edges_list,
                map_lines_list,
            )
            selected_edge_id = selected_edge.get("edge_id") if selected_edge else None
            if (
                selected_edge
                and selected_line_id
                and (
                    selected_edge_id != st.session_state.selected_network_edge_id
                    or selected_line_id != st.session_state.selected_network_line_id
                )
            ):
                st.session_state.selected_network_edge_id = selected_edge_id
                st.session_state.selected_network_line_id = selected_line_id
                st.rerun()
        elif mode == "Điểm đi" and new_pos != st.session_state.origin:
            st.session_state.origin = new_pos
            st.rerun()
        elif mode == "Điểm đến" and new_pos != st.session_state.dest:
            st.session_state.dest = new_pos
            st.rerun()
