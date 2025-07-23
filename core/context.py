# core/context.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class SoilInfo(BaseModel):
    pH: Optional[str] = None
    organic_matter: Optional[str] = None
    notes: Optional[str] = None

class LocationInfo(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class BasicInfo(BaseModel):
    crop_type: str
    area: float
    soil: Optional[SoilInfo] = None
    location: Optional[LocationInfo] = None

class PlantingGoal(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    seed_type: Optional[str] = None
    fertilizer: Optional[str] = None
    irrigation: Optional[str] = None
    target_yield: Optional[str] = None
    notes: Optional[str] = None

class RealtimeQA(BaseModel):
    date: Optional[str] = None
    question: Optional[str] = None
    image_uploaded: bool = False
    image_path: Optional[str] = None
    vision_analysis: Optional[Dict[str, str]] = None  # ← 已改为 dict

class WeatherDay(BaseModel):
    date: str
    temp_min: Optional[str]
    temp_max: Optional[str]
    text_day: Optional[str]
    precip: Optional[str]
    wind_dir: Optional[str]
    humidity: Optional[str]

class AgentContext(BaseModel):
    basic_info: BasicInfo
    planting_goal: PlantingGoal
    realtime_qa: Optional[RealtimeQA] = None
    weather_forecast: List[WeatherDay] = Field(default_factory=list)
    llm_response: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)

    def summarize_weather(self) -> str:
        if not self.weather_forecast:
            return "No weather data available（暂无天气数据）"
        return "\n".join([
            f"{w.date}：{w.text_day}，{w.temp_min}–{w.temp_max}℃，precipitation (meteorology)（降水） {w.precip}mm，humidity（湿度） {w.humidity}%，wind_dir（风向） {w.wind_dir}"
            for w in self.weather_forecast
        ])
