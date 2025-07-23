# main.py — Unified with visual model integration
import os
import streamlit as st

from modules.ui_input import (
    build_basic_inputs,
    build_goal_inputs,
    build_qa_inputs,
    save_bytes_to_temp,
)
from utils.context_utils import parse_ui_data, inject_weather
from modules.tool_dispatcher import (
    get_weather_forecast,
    get_weather_warnings,
    format_warning_text,
)
from modules.llm_planner import (
    generate_basic_planning_stream,
    generate_daily_schedule_stream,
    generate_realtime_answer_stream,
)
from modules.vision_analyzer import vision_analysis
from core.context import RealtimeQA

# ───────────── Initialize Session State ─────────────
DEFAULTS = {
    "context": None,
    "basic_summary": None,
    "daily_plan": None,
    "rt_answer": None,
    "weather7_text": None,
    "warning_text": None,
    "qa_image_bytes": None,
    "qa_image_suffix": ".png",
    "qa_image_path": None,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

st.set_page_config(page_title="AgriPlan‑Agent", layout="wide")
st.title("🌿 AgriPlan‑Agent Agricultural Planning Assistant（智能农事规划系统）")

# ───────────── Helper Functions ─────────────
def ensure_image_path() -> str | None:
    """If image bytes exist, save to a safe temporary path and return it（若有图像 bytes，则保存为安全路径）"""
    if not st.session_state["qa_image_bytes"]:
        return None

    if (p := st.session_state.get("qa_image_path")) and os.path.isfile(p):
        return p

    import uuid, tempfile

    safe_name = f"{uuid.uuid4().hex}{st.session_state['qa_image_suffix']}"
    safe_path = os.path.join(tempfile.gettempdir(), safe_name)
    with open(safe_path, "wb") as fw:
        fw.write(st.session_state["qa_image_bytes"])

    st.session_state["qa_image_path"] = safe_path
    return safe_path

def _is_file(path: str | None) -> bool:
    return isinstance(path, str) and os.path.isfile(path)

# ════════════════════ PART 1 ════════════════════
with st.container():
    basic_info = build_basic_inputs()

    if st.button("▶ Generate Part 1（生成第一部分）", type="primary"):
        if not basic_info["crop_type"]:
            st.error("Please provide crop type first（请先填写作物类型）")
            st.stop()

        ui_data = {"basic_info": basic_info, "planting_goal": {}, "realtime_qa": {}}
        ctx = parse_ui_data(ui_data)

        lat = ctx.basic_info.location.lat if ctx.basic_info.location else None
        lon = ctx.basic_info.location.lon if ctx.basic_info.location else None
        if lat is not None and lon is not None:
            w7 = get_weather_forecast(lat, lon, 7)
            inject_weather(ctx, w7)
            st.session_state["weather7_text"] = ctx.summarize_weather()
            st.session_state["warning_text"] = format_warning_text(get_weather_warnings(lat, lon))

        st.session_state["context"] = ctx

        st.markdown("#### ☁️ 7-Day Weather Forecast & Alerts（未来7天天气与预警信息）")
        st.code(st.session_state.get("weather7_text", "No data（暂无）"), language="markdown")
        st.code(st.session_state.get("warning_text", "No warning（暂无）"), language="markdown")

        placeholder = st.empty()
        acc = ""
        for delta in generate_basic_planning_stream(ctx):
            acc += delta
            placeholder.markdown(acc)
        placeholder.empty()
        st.session_state["basic_summary"] = acc
        st.success("✅ Part 1 Complete（第一部分完成）")

# Output of Part 1
if summary := st.session_state["basic_summary"]:
    st.markdown("### 📝 Result of Part 1（第一部分结果）")
    with st.expander("Click to expand/collapse（点击展开 / 收起）"):
        st.markdown(summary)

# ════════════════════ PART 2 ════════════════════
if st.session_state["context"]:
    with st.container():
        goal_info = build_goal_inputs()
        if st.button("▶ Generate Part 2（生成第二部分）"):
            ctx = st.session_state["context"]
            ctx.planting_goal = ctx.planting_goal.copy(update=goal_info)

            ph = st.empty()
            acc = ""
            for d in generate_daily_schedule_stream(ctx, st.session_state["basic_summary"]):
                acc += d
                ph.markdown(acc)
            ph.empty()
            st.session_state["daily_plan"] = acc
            st.success("✅ Part 2 Complete（第二部分完成）")

    if plan := st.session_state["daily_plan"]:
        st.markdown("### 📝 Result of Part 2（第二部分结果）")
        with st.expander("Click to expand/collapse（点击展开 / 收起）"):
            st.markdown(plan)

# ════════════════════ PART 3 ════════════════════
if st.session_state["context"]:
    with st.container():
        qa_info = build_qa_inputs()
        if st.button("▶ Generate Part 3（生成第三部分）"):
            ctx = st.session_state["context"]
            ctx.realtime_qa = (ctx.realtime_qa or RealtimeQA()).copy(update=qa_info)
            qa = ctx.realtime_qa

            qa.image_path = ensure_image_path()
            qa.image_uploaded = bool(qa.image_path)

            if qa.image_uploaded and qa.vision_analysis is None and _is_file(qa.image_path):
                with st.spinner("🔍 Running Visual Analysis（调用视觉模型）..."):
                    try:
                        qa.vision_analysis = vision_analysis(
                            image_path=qa.image_path, crop_type=ctx.basic_info.crop_type # type: ignore
                        )
                    except Exception as e:
                        st.error(f"Visual model failed: {e}（视觉模型调用失败）")

            if qa.vision_analysis:
                st.markdown("### 🖼️ Visual Analysis Results（图像分析结果）")

                def render_if_exists(label: str, key: str):
                    content = qa.vision_analysis.get(key) # type: ignore
                    if content:
                        st.markdown(f"#### {label}")
                        st.markdown(
                            f"<div style='background-color:#f9f9f9;padding:10px;border-radius:8px;border:1px solid #ddd'>{content}</div>",
                            unsafe_allow_html=True
                        )

                render_if_exists("📌 Image Summary（图像摘要）", "image_summary")
                render_if_exists("🌿 Growth Analysis（生长状况）", "growth_analysis")
                render_if_exists("🦠 Disease Detection（病害分析）", "disease_detection")

            ph3 = st.empty()
            acc3 = ""
            for d in generate_realtime_answer_stream(
                ctx,
                prev_summary=st.session_state["basic_summary"],
                prev_schedule=st.session_state.get("daily_plan"),
            ):
                acc3 += d
                ph3.markdown(acc3)
            ph3.empty()
            st.session_state["rt_answer"] = acc3
            st.success("✅ Part 3 Complete（第三部分完成）")

    if ans := st.session_state["rt_answer"]:
        st.markdown("### 📝 Result of Part 3（第三部分结果）")
        with st.expander("Click to expand/collapse（点击展开 / 收起）"):
            st.markdown(ans)

# ───────────── Footer ─────────────
st.divider()
st.caption("AgriPlan‑Agent © 2025")
