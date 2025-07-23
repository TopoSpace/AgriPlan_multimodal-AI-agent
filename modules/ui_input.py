# modules/ui_input.py

import streamlit as st
import datetime
from streamlit_folium import st_folium
import folium
import tempfile
import os
from io import BytesIO

os.makedirs("temp_images", exist_ok=True)

def save_bytes_to_temp(data: bytes, suffix: str = ".png") -> str:
    """Save bytes to temp image and return path（把 bytes 落盘为临时文件并返回路径）"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir="temp_images") as tmp:
        tmp.write(data)
        return tmp.name

def build_basic_inputs():
    st.markdown("### 📍 Part 1: Initial Planning (基本种植信息)")

    crop_type = st.text_input("Crop Type（作物类型）", placeholder="e.g. tobacco, rice, corn, etc.")
    area = st.number_input("Planting Area (mu)（种植面积，单位：亩）", min_value=0.0, step=0.1)

    st.markdown("#### (Optional) Soil Information（土壤信息，可选）")
    soil_ph = st.text_input("Soil pH Value（pH 值）", placeholder="e.g. 6.5")
    soil_organic = st.text_input("Organic Matter（有机质含量）", placeholder="e.g. medium, rich in compost, etc.")
    soil_notes = st.text_area("Additional Notes（备注）", placeholder="Any other soil-related description")

    st.markdown("#### Plot Location（地块位置）")
    location_name = st.text_input("Plot Name / ID（地块名称/编号）", placeholder="e.g. Xuchang-A01 (optional)")

    st.markdown("**Click the map to select plot location (latitude and longitude)（点击地图选择地块位置，经纬度）：**")
    m = folium.Map(location=[34.0, 113.8], zoom_start=7)
    m.add_child(folium.LatLngPopup())
    map_data = st_folium(m, height=400, width=700)
    latlon = map_data.get("last_clicked", {"lat": None, "lng": None})

    return {
        "crop_type": crop_type,
        "area": area,
        "soil": {
            "pH": soil_ph,
            "organic_matter": soil_organic,
            "notes": soil_notes
        },
        "location": {
            "name": location_name,
            "lat": latlon["lat"],
            "lon": latlon["lng"]
        }
    }

def build_goal_inputs():
    st.markdown("### 📅 Part 2: Daily Goal Setting（日程目标设定）")

    start_date = st.date_input("Expected Sowing Date（预期播种日期）", datetime.date.today(), key="goal_start")
    end_date = st.date_input("Expected Harvest Date（预期收获日期）", start_date + datetime.timedelta(days=60), key="goal_end")
    seed_type = st.text_input("Seed Type（使用苗种）", placeholder="e.g. Yunyan 85")
    fertilizer = st.text_input("Fertilizer Used（使用肥料）", placeholder="e.g. High-Nitrogen Compound")
    irrigation = st.selectbox("Irrigation Method（灌溉方式）", ["Drip", "Sprinkler", "Flood", "Other"])
    target_yield = st.text_input("Target Yield (kg/mu)（目标产量 kg/亩）", placeholder="e.g. 2500")
    plan_notes = st.text_area("Additional Notes（备注）", placeholder="e.g. water control in later stages")

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "seed_type": seed_type,
        "fertilizer": fertilizer,
        "irrigation": irrigation,
        "target_yield": target_yield,
        "notes": plan_notes
    }

def build_qa_inputs():
    st.markdown("### 💬 Part 3: Real-Time Q&A（实时问答与反馈）")

    current_date = st.date_input("Current Date（当前日期）", datetime.date.today(), key="qa_date")
    question = st.text_area("Your Question（你想询问的问题）", placeholder="e.g. Is today suitable for fertilization?", key="qa_question")

    uploaded_image = st.file_uploader("Upload Crop Image (Optional)（上传当前作物照片，可选）", type=["jpg", "jpeg", "png"], key="qa_image")

    # Cache bytes to session for downstream use
    if uploaded_image is not None:
        bytes_data = uploaded_image.getvalue()
        st.session_state["qa_image_bytes"] = bytes_data
        st.session_state["qa_image_suffix"] = os.path.splitext(uploaded_image.name)[-1] or ".png"

    return {
        "date": str(current_date),
        "question": question,
        "image_uploaded": "qa_image_bytes" in st.session_state,
        "image_path": None  # Will be set in main.py
    }
