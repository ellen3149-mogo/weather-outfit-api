\# 即時天氣與穿搭建議 API



\## 專案簡介

以 FastAPI 開發的輕量後端服務。使用者輸入縣市名稱，系統串接中央氣象署開放資料 API，

取得天氣預報後，依降雨機率與氣溫產生穿搭建議。未設定 API 金鑰時會自動使用 Mock 資料。



\## 應用情境

\- 通勤族出門前快速判斷要不要帶傘、穿什麼外套

\- 可整合至聊天機器人、行動 App 或智慧家居面板

\- 作為雲端無伺服器架構與第三方 API 串接的教學範例



\## 主要功能

\- `GET /weather-recommendation?city=臺北市`：回傳天氣概況與穿搭建議

\- `GET /`：健康檢查

\- 自動產生 Swagger 文件（`/docs`）

\- 相容「台／臺」輸入，並驗證縣市合法性

\- 第三方 API 失敗時回傳 502，查無資料回傳 404，錯誤處理明確

\- Mock 與真實資料模式自動切換



\## 範例回應

```json

{

&#x20; "city": "臺北市",

&#x20; "source": "CWA",

&#x20; "weather": {

&#x20;   "description": "陰短暫雨",

&#x20;   "rain\_probability": 80,

&#x20;   "min\_temp": 16,

&#x20;   "max\_temp": 21,

&#x20;   "comfort": "稍有寒意"

&#x20; },

&#x20; "recommendations": \[

&#x20;   "降雨機率高，請務必攜帶雨傘或穿著防水外套。",

&#x20;   "早晚偏涼，建議洋蔥式穿搭：長袖加薄外套。"

&#x20; ]

}

```



\## 雲端架構與服務選用原因

架構：API Gateway (HTTP API) → AWS Lambda (FastAPI + Mangum) → 中央氣象署 API，

金鑰存放於 SSM Parameter Store，日誌與監控使用 CloudWatch。

\- \*\*Lambda\*\*：流量小且不固定，按請求計費、免維運主機

\- \*\*API Gateway\*\*：託管 HTTPS、節流與授權

\- \*\*SSM / Secrets Manager\*\*：金鑰不寫入程式碼

\- \*\*CloudWatch\*\*：原生整合的日誌與告警

\- \*\*Mangum\*\*：同一份程式可在本機、容器、Lambda 間切換



\## 環境安裝與執行

```bash

\# 1. 建立虛擬環境

python -m venv venv

source venv/bin/activate        # Windows: venv\\Scripts\\activate



\# 2. 安裝套件

pip install -r requirements.txt



\# 3.（選用）設定氣象署金鑰，不設定則使用 Mock 資料

export CWA\_API\_KEY="你的授權碼"  # 至氣象署開放資料平台免費申請



\# 4. 啟動服務

uvicorn app.main:app --reload --port 8080



\# 5. 測試

curl "http://localhost:8080/weather-recommendation?city=臺北市"

\# 或開啟 http://localhost:8080/docs

```



\## 部署

\- \*\*Lambda\*\*：Handler 設為 `app.main.handler`，環境變數設定 `CWA\_API\_KEY`，前方接 API Gateway

\- \*\*容器\*\*：`docker build -t weather-api .` 後可部署至 App Runner 或 Cloud Run



\## 後續可擴充

快取（降低第三方 API 呼叫）、單元測試、CI/CD（GitHub Actions）、以 IaC（Terraform/SAM）管理基礎設施。

