# modules/tool_dispatcher.py

import requests
import yaml
import os
from typing import List, Dict, Tuple

# === Load Configuration ===
def load_weather_config():
    config_path = os.path.join("config", "settings.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["qweather"]

def _qweather_request(url: str) -> Dict:
    try:
        res = requests.get(url, timeout=8)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}

# === Get 7/30 day weather forecast ===
def get_weather_forecast(lat: float, lon: float, days: int = 7) -> List[Dict]:
    """
    Get the weather forecast for the next days (supports 7 or 30)
    Return format: [{date, temp_min, temp_max, text_day, precip, wind_dir, humidity}, ...].
    """
    if days not in (7, 30):
        raise ValueError("Only 7-day or 30-day forecast supported.")

    cfg = load_weather_config()
    key, host = cfg["apikey"], cfg["api_host"]
    location = f"{lon:.4f},{lat:.4f}"

    url = f"{host}/v7/weather/{days}d?location={location}&key={key}"
    raw = _qweather_request(url)

    if "daily" not in raw:
        return [{"error": f"No daily forecast returned: {raw}"}]

    forecast = []
    for day in raw["daily"][:days]:
        forecast.append({
            "date": day.get("fxDate"),
            "temp_min": day.get("tempMin"),
            "temp_max": day.get("tempMax"),
            "text_day": day.get("textDay"),
            "precip": day.get("precip"),
            "wind_dir": day.get("windDirDay"),
            "humidity": day.get("humidity")
        })
    return forecast

# === Get real-time weather alerts ===
def get_weather_warnings(lat: float, lon: float) -> List[Dict]:
    """
    Get the weather warning information of the current area (and the wind weather warning/now interface)
    Return Format: [{type, level, text, startTime, endTime}, ...]
    If there is no warning, return empty list
    """
    cfg = load_weather_config()
    key, host = cfg["apikey"], cfg["api_host"]
    location = f"{lon:.4f},{lat:.4f}"

    url = f"{host}/v7/warning/now?location={location}&key={key}"
    raw = _qweather_request(url)

    if "warning" not in raw:
        return []

    warnings = []
    for w in raw["warning"]:
        warnings.append({
            "type": w.get("typeName", ""),
            "level": w.get("level", ""),
            "text": w.get("text", ""),
            "startTime": w.get("startTime", ""),
            "endTime": w.get("endTime", "")
        })
    return warnings

# === Convenient formatting functions (available for prompt)===
def format_warning_text(warnings: List[Dict]) -> str:
    if not warnings:
        return "No weather warning at this time.（暂无天气预警。）"
    lines = []
    for w in warnings:
        line = f"{w.get('type','')}(level（等级）:{w.get('level','')}) - {w.get('text','')}"
        if w.get("startTime"):
            line += f"（startTime（开始）：{w['startTime']}）"
        lines.append(line)
    return "\n".join(lines)
