# utils/context_utils.py

from core.context import (
    AgentContext, BasicInfo, SoilInfo, LocationInfo,
    PlantingGoal, RealtimeQA
)

def parse_ui_data(ui_data: dict) -> AgentContext:
    """Secure conversion of UI data to AgentContext, with missing keys filled in with default values."""
    b = ui_data.get("basic_info", {}) or {}
    pg = ui_data.get("planting_goal", {}) or {}
    rq = ui_data.get("realtime_qa", {}) or {}

    return AgentContext(
        basic_info=BasicInfo(
            crop_type=b.get("crop_type", ""),
            area=b.get("area", 0.0),
            soil=SoilInfo(**(b.get("soil", {}) or {})),
            location=LocationInfo(**(b.get("location", {}) or {}))
        ),
        planting_goal=PlantingGoal(**pg),
        realtime_qa=RealtimeQA(
            date=rq.get("date"),
            question=rq.get("question"),
            image_uploaded=rq.get("image_uploaded", False),
            image_path=rq.get("image_path"),
            vision_analysis=rq.get("vision_analysis")
        )
    )


from core.context import AgentContext, WeatherDay

def inject_weather(context: AgentContext, weather_data: list):
    """Write the data returned by the weather API to AgentContext.weather_forecast"""
    weather_list = []
    for day in weather_data:
        weather = WeatherDay(
            date=day.get("date", ""),
            temp_min=day.get("temp_min", ""),
            temp_max=day.get("temp_max", ""),
            text_day=day.get("text_day", ""),
            precip=day.get("precip", ""),
            wind_dir=day.get("wind_dir", ""),
            humidity=day.get("humidity", "")
        )
        weather_list.append(weather)
    context.weather_forecast = weather_list

