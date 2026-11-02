"""
即時天氣與穿搭建議 API
- 框架：FastAPI
- 資料來源：中央氣象署開放資料 F-C0032-001（一般天氣預報-36 小時天氣預報）
- 未設定 CWA_API_KEY 時，自動切換為 Mock 資料，方便本機展示與測試
- 透過 Mangum 轉接器，同一份程式可部署到 AWS Lambda，也可用 uvicorn 當一般服務跑
"""
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from mangum import Mangum
from pydantic import BaseModel

# ---------- 設定區：全部從環境變數讀取，避免金鑰寫死在程式碼 ----------
CWA_API_KEY = os.getenv("CWA_API_KEY", "")  # 空字串 => 使用 Mock 模式
CWA_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
REQUEST_TIMEOUT = 8.0  # 呼叫第三方 API 的逾時秒數

# 氣象署 36 小時預報涵蓋的 22 個縣市
VALID_CITIES = {
    "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市",
    "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市",
    "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣",
}

app = FastAPI(
    title="即時天氣與穿搭建議 API",
    description="輸入縣市名稱，回傳天氣概況與穿搭建議",
    version="1.0.0",
)


# ---------- 回應資料模型（同時會自動產生 Swagger 文件） ----------
class WeatherInfo(BaseModel):
    description: str      # 天氣現象，例如「多雲時陰」
    rain_probability: int  # 降雨機率 %
    min_temp: int         # 最低溫 °C
    max_temp: int         # 最高溫 °C
    comfort: str          # 舒適度，例如「舒適」


class RecommendationResponse(BaseModel):
    city: str
    source: str           # "CWA" 或 "MOCK"，讓呼叫端知道資料來源
    weather: WeatherInfo
    recommendations: list[str]


# ---------- 工具函式 ----------
def normalize_city(name: str) -> str:
    """把使用者輸入的「台」統一轉成官方用字「臺」，並去除空白。"""
    return name.strip().replace("台", "臺")


def get_mock_weather(city: str) -> WeatherInfo:
    """Mock 資料：用縣市名稱的 hash 產生穩定、可重現的假資料（同一縣市結果固定）。"""
    seed = sum(ord(c) for c in city)
    min_t = 10 + seed % 15            # 10 ~ 24 °C
    return WeatherInfo(
        description=["晴時多雲", "多雲時陰", "陰短暫雨", "陰有雨"][seed % 4],
        rain_probability=(seed * 7) % 100,
        min_temp=min_t,
        max_temp=min_t + 4 + seed % 5,
        comfort=["寒冷", "稍有寒意", "舒適", "悶熱"][seed % 4],
    )


async def fetch_cwa_weather(city: str) -> WeatherInfo:
    """呼叫氣象署 API 並解析出第一個時段（最近 12 小時）的預報。"""
    params = {"Authorization": CWA_API_KEY, "locationName": city}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(CWA_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        # 第三方服務失敗 => 回 502 Bad Gateway，語意上最貼切
        raise HTTPException(status_code=502, detail=f"氣象署 API 呼叫失敗：{exc}")

    locations = data.get("records", {}).get("location", [])
    if not locations:
        raise HTTPException(status_code=404, detail=f"查無 {city} 的天氣資料")

    # 把 weatherElement 轉成 {元素名稱: 第一個時段的值} 的字典，方便取用
    elements = {
        e["elementName"]: e["time"][0]["parameter"]["parameterName"]
        for e in locations[0]["weatherElement"]
    }
    return WeatherInfo(
        description=elements["Wx"],
        rain_probability=int(elements["PoP"]),
        min_temp=int(elements["MinT"]),
        max_temp=int(elements["MaxT"]),
        comfort=elements["CI"],
    )


def build_recommendations(w: WeatherInfo) -> list[str]:
    """穿搭規則引擎：依降雨機率與溫度產生建議。規則集中在此，日後易於擴充。"""
    tips: list[str] = []

    # --- 降雨 ---
    if w.rain_probability >= 70:
        tips.append("降雨機率高，請務必攜帶雨傘或穿著防水外套。")
    elif w.rain_probability >= 40:
        tips.append("可能下雨，建議隨身帶一把折疊傘。")
    else:
        tips.append("降雨機率低，不需特別準備雨具。")

    # --- 氣溫（以最低溫判斷保暖需求，以最高溫判斷防曬／透氣）---
    if w.min_temp <= 14:
        tips.append("氣溫偏低，建議穿大衣或厚外套，搭配圍巾保暖。")
    elif w.min_temp <= 20:
        tips.append("早晚偏涼，建議洋蔥式穿搭：長袖加薄外套。")
    else:
        tips.append("氣溫舒適，短袖或薄長袖即可。")

    if w.max_temp >= 30:
        tips.append("白天炎熱，選擇透氣排汗衣物，並注意防曬與補充水分。")

    # --- 日夜溫差 ---
    if w.max_temp - w.min_temp >= 8:
        tips.append("日夜溫差大，建議多帶一件可穿脫的外套。")

    return tips


# ---------- API 端點 ----------
@app.get("/", tags=["health"])
async def health_check():
    """健康檢查端點：負載平衡器／容器平台可用它確認服務存活。"""
    return {"status": "ok", "mode": "CWA" if CWA_API_KEY else "MOCK"}


@app.get(
    "/weather-recommendation",
    response_model=RecommendationResponse,
    tags=["weather"],
    summary="取得縣市天氣與穿搭建議",
)
async def weather_recommendation(
    city: str = Query(..., description="縣市名稱，例如：臺北市、高雄市", min_length=2),
):
    city = normalize_city(city)
    if city not in VALID_CITIES:
        raise HTTPException(status_code=400, detail=f"不支援的縣市：{city}")

    # 有金鑰 => 呼叫真實 API；沒有 => Mock
    if CWA_API_KEY:
        weather: WeatherInfo = await fetch_cwa_weather(city)
        source = "CWA"
    else:
        weather = get_mock_weather(city)
        source = "MOCK"

    return RecommendationResponse(
        city=city,
        source=source,
        weather=weather,
        recommendations=build_recommendations(weather),
    )


# ---------- AWS Lambda 進入點 ----------
# API Gateway 的事件會被 Mangum 轉成 ASGI 請求交給 FastAPI；本機用 uvicorn 時不會用到
handler = Mangum(app)