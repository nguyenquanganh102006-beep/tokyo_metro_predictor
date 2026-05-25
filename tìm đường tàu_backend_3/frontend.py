import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

# --- CẤU HÌNH HỆ THỐNG ---
API_BASE = "http://127.0.0.1:8000/api"
st.set_page_config(page_title="Tokyo Subway Pathfinder", layout="wide", page_icon="🚇")

# Khởi tạo Session State để lưu dữ liệu khi reload trang
if "token" not in st.session_state: st.session_state.token = None
if "role" not in st.session_state: st.session_state.role = "user"
if "origin" not in st.session_state: st.session_state.origin = [35.6812, 139.7671]
if "dest" not in st.session_state: st.session_state.dest = [35.6586, 139.7454]
if "path_data" not in st.session_state: st.session_state.path_data = None
if "map_lang" not in st.session_state: st.session_state.map_lang = "en"

def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

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

def draw_routes(m, lang):
    """Vẽ routes trên bản đồ"""
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
                    tooltip=f"{stp.get('line_name', 'Tàu điện')} ({stp.get('distance_km')} km)"
                ).add_to(m)
                
                folium.CircleMarker(p1, radius=4, color="white", fill=True, fill_color=line_color).add_to(m)
                folium.CircleMarker(p2, radius=4, color="white", fill=True, fill_color=line_color).add_to(m)
    
    folium.Marker(st.session_state.origin, icon=folium.Icon(color='green', icon='play'), tooltip="Điểm đi").add_to(m)
    folium.Marker(st.session_state.dest, icon=folium.Icon(color='red', icon='stop'), tooltip="Điểm đến").add_to(m)
    return m

def create_map(lang):
    """Tạo bản đồ (lang: 'ja' hoặc 'en')"""
    if lang == "en":
        m = folium.Map(location=[35.6895, 139.6917], zoom_start=12, tiles='CartoDB positron')
    else:
        m = folium.Map(location=[35.6895, 139.6917], zoom_start=12)  # OpenStreetMap - Tiếng Nhật
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

        st.write("#### ✍️ Nhập điểm đi / điểm đến")
        in_col1, in_col2 = st.columns(2)
        with in_col1:
            origin_place_input = st.text_input(
                "Điểm đi",
                placeholder="Ví dụ: Tokyo Station",
                key="origin_place_input",
            )
        with in_col2:
            dest_place_input = st.text_input(
                "Điểm đến",
                placeholder="Ví dụ: Shibuya Crossing",
                key="dest_place_input",
            )
        if st.button("📌 Áp dụng địa điểm", use_container_width=True):
            origin_geo = geocode_place(origin_place_input)
            dest_geo = geocode_place(dest_place_input)
            if not origin_geo or not dest_geo:
                st.error("❌ Không tìm thấy một trong hai địa điểm. Hãy nhập rõ hơn hoặc chọn trên bản đồ.")
            else:
                st.session_state.origin = [origin_geo["lat"], origin_geo["lon"]]
                st.session_state.dest = [dest_geo["lat"], dest_geo["lon"]]
                st.session_state.path_data = None
                st.rerun()

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
                for i, group in enumerate(line_groups, 1):
                    first_step = group[0]
                    last_step = group[-1]
                    
                    total_distance = sum(s.get('distance_km', 0) for s in group)
                    total_fare = sum(s.get('fare_yen', 0) for s in group)
                    line_color = first_step.get('line_color', '#2E86C1')
                    
                    with st.expander(f"🚇 **{first_step.get('line_name')}**: {first_step['from_station']} → {last_step['to_station']} | 📏 {total_distance:.1f} km"):
                        for j, step in enumerate(group, 1):
                            transfer_tag = " 🔀" if step.get('is_transfer') else ""
                            st.caption(f"  {j}. {step['from_station']} → {step['to_station']} | {step.get('distance_km')} km | {step.get('fare_yen')} ¥{transfer_tag}")


        if st.session_state.role == "admin":
            with st.expander("🛠️ Quản trị (Admin)"):
                # --- Phần 1: Chọn ga để cấm/mở ---
                st.subheader("📍 Quản lý Ga")
                try:
                    stations_res = requests.get(f"{API_BASE}/stations/", headers=get_headers())
                    stations_list = stations_res.json() if stations_res.status_code == 200 else []
                except:
                    stations_list = []

                if stations_list:
                    s_map = {f"{s.get('station_name')} (ID: {s.get('station_id')})": s.get('station_id') for s in stations_list}
                    sel_s = st.selectbox("Chọn ga cần thao tác", options=list(s_map.keys()))
                    col_btn1, col_btn2 = st.columns(2)
                    if col_btn1.button("🚫 Chặn ga này", use_container_width=True):
                        requests.post(f"{API_BASE}/admin/station/ban", json={"station_id": s_map[sel_s]}, headers=get_headers())
                        st.toast(f"Đã chặn ga {sel_s}")
                        st.rerun()
                    if col_btn2.button("✅ Mở ga này", use_container_width=True):
                        requests.post(f"{API_BASE}/admin/station/unban", json={"station_id": s_map[sel_s]}, headers=get_headers())
                        st.toast(f"Đã mở ga {sel_s}")
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
                        for station in banned_stations:
                            st.caption(f"✅ 🚇 {station.get('station_name')} (ID: {station.get('station_id')})")
                    else:
                        for station in banned_stations:
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
                    
                    if selected_to_unban_stations:
                        if st.button("✅ Mở các ga được chọn", use_container_width=True, key="unban_selected_stations"):
                            for station in selected_to_unban_stations:
                                requests.post(f"{API_BASE}/admin/station/unban", 
                                            json={"station_id": station['station_id']}, 
                                            headers=get_headers())
                            st.success(f"✅ Đã mở {len(selected_to_unban_stations)} ga!")
                            st.rerun()
                else:
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
                    sel_l = st.selectbox("Chọn tuyến cần thao tác", options=list(l_map.keys()), key="line_select")
                    col_btn3, col_btn4 = st.columns(2)
                    if col_btn3.button("🚫 Chặn tuyến này", use_container_width=True):
                        requests.post(f"{API_BASE}/admin/line/ban", json={"line_id": l_map[sel_l]}, headers=get_headers())
                        st.toast(f"Đã chặn tuyến {sel_l}")
                        st.rerun()
                    if col_btn4.button("✅ Mở tuyến này", use_container_width=True):
                        requests.post(f"{API_BASE}/admin/line/unban", json={"line_id": l_map[sel_l]}, headers=get_headers())
                        st.toast(f"Đã mở tuyến {sel_l}")
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
                            st.rerun()
                else:
                    st.info("✅ Không có tuyến nào bị đóng")

with right_col:
    st.write("### 🗺️ Bản đồ")
    mode = st.radio("Chọn vị trí trên bản đồ:", ["Điểm đi", "Điểm đến"], horizontal=True, key="mode_select")
    m = create_map(st.session_state.map_lang)
    out = st_folium(m, width=None, height=820, key=f"map_{st.session_state.map_lang}", returned_objects=["last_clicked"])

    if out and out.get("last_clicked"):
        new_pos = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
        if mode == "Điểm đi" and new_pos != st.session_state.origin:
            st.session_state.origin = new_pos
            st.rerun()
        elif mode == "Điểm đến" and new_pos != st.session_state.dest:
            st.session_state.dest = new_pos
            st.rerun()