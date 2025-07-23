# modules/llm_planner.py
# LLM Access (Synchronous + Streaming) - Full Available Version
# pip install openai==1.* tenacity pyyaml

from typing import Optional, List, Dict, Iterable
import os, yaml
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)
from core.context import AgentContext
from modules.tool_dispatcher import (
    get_weather_forecast,
    get_weather_warnings,
    format_warning_text,
)

# ───────────────────────── 1. LLM(e.g. DeepSeek) Deployment ──────────────────────────
def _load_llm_cfg() -> Dict[str, str]:
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    llm_cfg = cfg.get("llm", {})
    return {
        "api_key": llm_cfg.get("apikey", os.getenv("DEEPSEEK_API_KEY", "")),
        "base_url": llm_cfg.get("api_host", "https://api.deepseek.com"),
        "model_chat": llm_cfg.get("model_chat", "deepseek-chat"),
        "model_reason": llm_cfg.get("model_reason", "deepseek-reasoner"),
    }


_LLM = _load_llm_cfg()
_client = OpenAI(api_key=_LLM["api_key"], base_url=_LLM["base_url"])

# ───────────────────────── 2. universal package ──────────────────────────
class LLMError(Exception):
    """Packaging Unified LLM Call Exception"""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((LLMError, TimeoutError)),
)
def _chat_completion(
    messages: List[ChatCompletionMessageParam],
    model: str,
    temperature: float = 0.4,
) -> str:
    """Synchronized calls to LLM Chat"""
    try:
        resp: ChatCompletion = _client.chat.completions.create(  # type: ignore
            model=model,
            messages=messages,
            temperature=temperature,
            stream=False,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:  # pragma: no cover
        raise LLMError(str(e))


def _stream_completion(
    messages: List[ChatCompletionMessageParam],
    model: str,
    temperature: float = 0.4,
) -> Iterable[str]:
    """流式生成器：yield delta.content"""
    try:
        stream = _client.chat.completions.create(  # type: ignore
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:  # type: ignore # type: ChatCompletionChunk
            if chunk.choices and (delta := chunk.choices[0].delta.content):
                yield delta
    except Exception as e:  # pragma: no cover
        raise LLMError(str(e))


def _make_messages(sys_prompt: str, user_prompt: str) -> List[ChatCompletionMessageParam]:
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_llm(
    prompt: str,
    *,
    sys_prompt: str = "You are an expert agronomist assistant, answer clearly and concisely.",
    use_reasoner: bool = False,
    temperature: float = 0.4,
) -> str:
    model = _LLM["model_reason"] if use_reasoner else _LLM["model_chat"]
    return _chat_completion(_make_messages(sys_prompt, prompt), model, temperature)


def call_llm_stream(
    prompt: str,
    *,
    sys_prompt: str = "You are an expert agronomist assistant, answer clearly and concisely.",
    use_reasoner: bool = False,
    temperature: float = 0.4,
) -> Iterable[str]:
    model = _LLM["model_reason"] if use_reasoner else _LLM["model_chat"]
    return _stream_completion(_make_messages(sys_prompt, prompt), model, temperature)


# ───────────────────────── 3. Prompt build tool ──────────────────────────
def _fmt_weather(wlist: List[Dict]) -> str:
    if not wlist:
        return "No weather data is available at this time.（暂无天气数据。）"
    return "\n".join(
        f"{w['date']}：{w.get('text_day','')}"
        f" {w.get('temp_min','?')}–{w.get('temp_max','?')}℃"
        f" precipitation (meteorology)（降水）{w.get('precip','?')}mm humidity（湿度）{w.get('humidity','?')}%"
        for w in wlist
    )


# ---------- PART‑1 ：Initial planting plan ----------
def build_prompt_basic(ctx: AgentContext) -> str:
    lat = ctx.basic_info.location.lat if ctx.basic_info.location else None
    lon = ctx.basic_info.location.lon if ctx.basic_info.location else None

    weather7: List[Dict] = []
    warning_txt = "There are no weather warnings at this time.（暂无天气预警。）"
    if lat is not None and lon is not None:
        weather7 = get_weather_forecast(lat, lon, 7)
        warnings = get_weather_warnings(lat, lon)
        warning_txt = format_warning_text(warnings)

    p: List[str] = [
        "You are an intelligent agricultural planning assistant with strong domain knowledge. Based on the following contextual information, please generate a practical, low-intervention, and climate-aware **overall planting plan**.（你是一名经验丰富的农业智能助手，请基于以下信息制定一份科学、现实、避免过度人工干预的 {{ crop_name }} 种植整体规划方案。）\n",
        f"【Crop Type（作物类型）】{ctx.basic_info.crop_type}",
        f"【Planted Area（种植面积）】{ctx.basic_info.area} acres（亩）",
    ]

    soil = ctx.basic_info.soil
    if soil:
        if soil.pH:
            p.append(f"【Soil pH（土壤 pH）】{soil.pH}")
        if soil.organic_matter:
            p.append(f"【Soil Organic Matter Content（有机质含量）】{soil.organic_matter}")
        if soil.notes:
            p.append(f"【Remarks on Soil（土壤备注）】{soil.notes}")

    loc = ctx.basic_info.location
    if loc:
        if loc.name:
            p.append(f"【Name of Planting Plot（地块名称）】{loc.name}")
        if lat is not None and lon is not None:
            p.append(f"【Geographic Coordinates（坐标）】{lat:.6f}, {lon:.6f}")

    p.append("\n【7-day weather forecast（未来 7 天天气）】")
    p.append(_fmt_weather(weather7))
    p.append("\n【Weather Warning（天气预警）】")
    p.append(warning_txt)
    p.append(
    "\n【Output Requirements 输出要求】\n"
    "Please output in **English** with a clear and structured layout. Use bullet points or numbered lists where appropriate.\n\n"
    "请使用 **英文** 输出，语言要专业、易于农业工作者理解，格式清晰，有条理，便于展示与执行。请按如下内容生成：\n\n"
    "1. ✅ **Crop Suitability Analysis 作物适宜性分析**  \n"
    "   Evaluate whether the current environment supports planting, considering soil, climate, and history.\n\n"
    "2. 📅 **Suggested Sowing Period 推荐播种时段**  \n"
    "   Specify a suitable sowing window with brief justification.\n\n"
    "3. 🌱 **Planting Method 种植方式建议**  \n"
    "   Recommend spacing, density, and auxiliary needs (e.g., mulch, greenhouse).\n\n"
    "4. 📈 **Key Growth Phase Management 关键管理阶段**  \n"
    "   Outline key agricultural activities at different stages (e.g., seedling, elongation, heading).\n\n"
    "5. ⚠️ **Risks & Cautions 风险提示**  \n"
    "   Gently point out any risks (e.g., extreme weather, poor drainage), avoiding exaggerated language.\n\n"
    "6. 🛠️ **Intervention Recommendations 人工干预建议**  \n"
    "   ONLY suggest necessary manual actions (e.g., basic irrigation/fertilization). If no action is needed, clearly state \"No extra intervention is required at this stage.\"\n\n"
    "7. ✅ **Conclusion 总结建议**  \n"
    "   Conclude with a short summary suitable for implementation.\n\n"
    "Avoid unnecessary complexity. Do **not** recommend specific commercial products unless asked. Stay grounded in agricultural practice and weather constraints.\n"
)


    return "\n".join(p)


def generate_basic_planning(ctx: AgentContext) -> str:
    return call_llm(build_prompt_basic(ctx))


def generate_basic_planning_stream(ctx: AgentContext) -> Iterable[str]:
    return call_llm_stream(build_prompt_basic(ctx))


# ---------- PART‑2 ：a day-by-day agricultural program ----------
def build_prompt_schedule(ctx: AgentContext, prev_summary: Optional[str] = None) -> str:
    p: List[str] = [
        "You are an expert agricultural grower, develop a day-by-day farm operation plan based on the following information:（你是一位农业种植专家，请基于以下信息制定逐日农事操作计划：）\n",
        f"【Crop Type（作物类型）】{ctx.basic_info.crop_type}",
        f"【Planted Area（种植面积）】{ctx.basic_info.area} acres（亩）",
    ]

    if prev_summary:
        p.append("\n【Planting Suitability Conclusions（种植适宜性结论）】")
        p.append(prev_summary)

    # Targeted Planting Information
    g = ctx.planting_goal
    p.extend(
        [
            "\n【Targeted Planting Information（目标种植信息）】",
            f"- Starting planting date:（起始种植日期：）{g.start_date or '-'}",
            f"- Expected harvest date:（预期收获日期：）{g.end_date or '-'}",
            f"- Use of seedlings:（使用苗种：）{g.seed_type or '-'}",
            f"- Use of fertilizers:（使用肥料：）{g.fertilizer or '-'}",
            f"- Irrigation methods:（灌溉方式：）{g.irrigation or '-'}",
            f"- Target yield:（目标产量：）{g.target_yield or '-'}",
            f"- Remarks/Notes:（备注：）{g.notes or '-'}",
        ]
    )

    # 30-day weather forecast
    lat = ctx.basic_info.location.lat if ctx.basic_info.location else None
    lon = ctx.basic_info.location.lon if ctx.basic_info.location else None
    weather30: List[Dict] = get_weather_forecast(lat, lon, 30) if (lat and lon) else []
    p.append("\n【30-day weather forecast（未来 30 天天气）】")
    p.append(_fmt_weather(weather30))

    p.append(
    "\n【Output Requirements 输出要求】\n"
    "Please output in **English**, structured in a **day-by-day calendar style**, clearly listing operations for each day.\n\n"
    "请使用英文输出，以“逐日计划卡片”形式输出内容，清晰呈现每日的关键农业操作。每日建议应涵盖以下方面：\n\n"
    "1. 📅 **Date 日期**  \n"
    "   Specify the operation date (e.g., July 25).\n\n"
    "2. 🌤️ **Weather Info 天气信息**  \n"
    "   Briefly state the weather (already provided above, no need to infer).\n\n"
    "3. 🌾 **Key Operation 农业操作**  \n"
    "   Suggest the main task for the day (e.g., soil preparation, irrigation, transplanting, fertilization).\n\n"
    "4. ⚠️ **Caution 注意事项**  \n"
    "   Mention any potential concerns or observations based on weather or growth stage.\n\n"
    "5. 🛠️ **Manual Intervention 人工干预建议**  \n"
    "   Only recommend necessary operations. If nothing is needed, write: \"No manual operation required today.\"\n\n"
    "Please keep each day’s description short and practical. Limit to one paragraph per day.\n\n"
    "Avoid generic language. Tailor the plan to current crop stage, soil and weather context. Do not recommend unnecessary tasks."
)

    return "\n".join(p)


def generate_daily_schedule(ctx: AgentContext, prev_summary: Optional[str]) -> str:
    return call_llm(build_prompt_schedule(ctx, prev_summary))


def generate_daily_schedule_stream(ctx: AgentContext, prev_summary: Optional[str]) -> Iterable[str]:
    return call_llm_stream(build_prompt_schedule(ctx, prev_summary))


# ---------- PART‑3 ：realtime_qa ----------
def build_prompt_realtime_qa(
    ctx: AgentContext,
    prev_summary: Optional[str] = None,
    prev_schedule: Optional[str] = None,
) -> str:
    qa = ctx.realtime_qa
    assert qa, "RealtimeQA should not be empty（不应为空）"

    p: List[str] = ["You are a farm advisor, answer the farmer's question in context:（你是一位农事顾问，请结合上下文回答农民问题：）\n"]

    if prev_summary:
        p.append("【Prior Suitability Conclusions（前期适宜性结论）】")
        p.append(prev_summary)
    if prev_schedule:
        p.append("\n【Previous Daily Farming Program（前期逐日农事计划）】")
        p.append(prev_schedule)

    p.append(f"\n【Current Date（当前日期）】{qa.date}")
    p.append(f"【Questions from farmers（农民提问）】{qa.question}")

    # 图像分析
    if isinstance(qa.vision_analysis, dict) and qa.vision_analysis:
        v = qa.vision_analysis
        p.append("\n【Image Recognition Results（图像识别结果）】")
        if v.get("image_summary"):
            p.append(f"- image summary（图像摘要）：{v['image_summary']}")
        if v.get("growth_analysis"):
            p.append(f"- growth analysis（生长状况）：{v['growth_analysis']}")
        if v.get("disease_detection"):
            p.append(f"- disease detection（病虫害检测）：{v['disease_detection']}")

    # 当天天气
    lat = ctx.basic_info.location.lat if ctx.basic_info.location else None
    lon = ctx.basic_info.location.lon if ctx.basic_info.location else None
    today_weather = ""
    warn_txt = "There are no weather warnings at this time.（暂无天气预警。）"
    if lat is not None and lon is not None:
        weather7 = get_weather_forecast(lat, lon, 7)
        today_weather = _fmt_weather(weather7[:1])
        warn_txt = format_warning_text(get_weather_warnings(lat, lon))

    p.append("\n【Today's weather（当天天气）】")
    p.append(today_weather or "No weather data available（暂无天气数据）")
    p.append("\n【weather warning（天气预警）】")
    p.append(warn_txt)

    p.append(
    "\n【Output Requirements 输出要求】\n"
    "You are acting as a **smart agricultural assistant** that provides helpful, precise, and grounded responses to farmers’ questions in real-time.\n\n"
    "你现在是一个农业智能助手，需要实时回答农户提出的具体问题。请确保：\n\n"
    "1. 🤖 **Grounded Reasoning 基于上下文推理**  \n"
    "   Always refer to the known planting context (crop, soil, weather, prior plans). Do not fabricate.\n\n"
    "2. 📸 **Image Understanding 图像理解（如有）**  \n"
    "   If an image is uploaded, analyze crop condition from the photo (growth, diseases, pests) and provide insights accordingly.\n\n"
    "3. 🧑‍🌾 **Farmer-Friendly Language 语言友好**  \n"
    "   Keep your explanation accurate yet easy to follow for agricultural workers.\n\n"
    "4. ⚠️ **Avoid Over-intervention 避免过度干预**  \n"
    "   Only recommend manual intervention if absolutely necessary. Otherwise, say \"No intervention needed for now.\"\n\n"
    "5. 🌱 **Link to Current Stage 与当前阶段联动**  \n"
    "   Make sure your suggestions are consistent with the current stage of growth and prior planning.\n\n"
    "【If Image is Provided 图片分析要求】\n"
    "Please include a section:\n"
    "**🔍 Image Diagnosis 图像诊断**:\n"
    "- Describe crop growth visually.\n"
    "- Identify possible symptoms or issues.\n"
    "- Suggest action or note \"No visible issue.\"\n\n"
    "【General Rule 通用规则】\n"
    "- Avoid generic or copy-paste responses.\n"
    "- Answer in **English** with professional and structured format.\n"
    "- Limit each reply to 2-3 well-written paragraphs or bullet points.\n"
)

    return "\n".join(p)


def generate_realtime_answer(
    ctx: AgentContext,
    prev_summary: Optional[str] = None,
    prev_schedule: Optional[str] = None,
) -> str:
    return call_llm(build_prompt_realtime_qa(ctx, prev_summary, prev_schedule), temperature=0.5)


def generate_realtime_answer_stream(
    ctx: AgentContext,
    prev_summary: Optional[str] = None,
    prev_schedule: Optional[str] = None,
) -> Iterable[str]:
    return call_llm_stream(build_prompt_realtime_qa(ctx, prev_summary, prev_schedule), temperature=0.5)
