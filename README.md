# Genetic Algorithm TSP · Dispatch Lab

把飯店／送餐機器人的訂單、重要程度和等待風險，轉成可互動觀察的配送順序。使用 **A* 避牆路徑 + PMX 基因演算法 + Sower 多世界菁英交換**，並保留原始研究 notebooks 作為教學比較。

## 快速啟動（Conda）

已安裝 Miniconda 或 Anaconda 後：

```bash
git clone https://github.com/a0665x/Genetic_Algorithm_TSP.git
cd Genetic_Algorithm_TSP
conda env create -f environment.yml
conda activate dispatch-lab
python app.py
```

瀏覽器開啟 **http://127.0.0.1:8000**。不需 GPU、Node.js、npm、前端 build 或網路 CDN。地圖與訂單在本機運算，範例 PNG 已附在 `data/map/`。

已有 repo：

```bash
git pull origin main
conda env update -f environment.yml --prune
conda activate dispatch-lab
python app.py --port 8000
```

替代 venv 安裝（Python 3.11+）：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

預設只監聽本機。這是無登入的本機模擬工具，非公開多使用者服務。如需可信內網訪問，可自行指定 `--host 0.0.0.0`，應使用網路存取控制；正式部署需另加驗證、反向代理與工作佇列。

## 兩分鐘體驗

1. 預設載入飯店地圖與 10 筆示範訂單；也可切換餐廳、倉儲。
2. 地圖選擇「訂單節點」後點擊客房或通道；「起點」指定機器人位置。「移動節點」先點訂單再點新位置；「刪除節點」點選要刪除的訂單。
3. 訂單表可新增、刪除、編輯 ID、X/Y、重要度、已等待秒數、耐久度、棄單風險、附近速度、服務時間和禁止順位。
4. 按 **GA 排程規劃**。先計算 A* 矩陣，再進化並更新圖表。所有配送線沿 costmap 可通行路徑繪製。
5. 點擊世界卡片切換路線；用世代滑桿／回放觀看每一代的最佳順序，虛線為 Sower 交換世代。
6. 查看到達時間、逾時量、權重明細，以及 W（重要度）、D（米）、T（秒）矩陣。匯出訂單／結果 JSON，供重現與分析。

修改地圖、節點或參數會清除舊規劃，避免新輸入與舊結果混淆。計算期間鎖定輸入，可按停止中斷。若沒有路徑或順位約束互相衝突，會直接顯示原因，而不畫一條穿牆替代線。

## 地圖、速度與安全邊界

| 項目 | 規則 |
|---|---|
| 上傳格式 | PNG、JPG、PGM、BMP，最大 2 MB；每邊 4–512 px |
| 座標 | 左上角 `(0,0)`，x 向右，y 向下，像素中心 |
| 灰階 | ≤ 障礙閾值視為牆；255 為白色通道；中間值增加成本 |
| 透明像素 | 合成黑底，視為障礙 |
| 解析度 | m/px，範例預設 0.1；上傳地圖請依來源設定 |
| 機器人半徑 | 按格子向上取整作保守方形膨脹，含地圖邊界 |
| 斜走 | 8 鄰接，但不能穿過两個障礙物之間的斜角 |
| 節點慢速 | 目的地附近指定半徑內採用該訂單速度上限 |
| 不可達 | 整次規劃失敗並指出節點；不默默丟掉訂單 |

較大地圖請事先依機器人需求產生適合的低解析度 occupancy grid，**不要用平滑縮圖把細牆消掉**。本版不自動解析 ROS YAML、不處理地圖 origin/rotation、未知區域需自行轉為障礙。這是静態網格模擬，不是直接控制真實機器人的避障控制器。

## 權重與 sigmoid

$$\sigma(z)=\frac{1}{1+e^{-z}},\quad w_j=1+9\sigma(z_j)$$

$$z_j=b+a_I I_j/10+a_W\min(W_j/P_j,3)+a_R R_j+a_D\min(d_{0j}/50,3)+a_V(1-\min(v_j,v_0)/v_0)$$

| 符號 | 訂單欄位／來源 |
|---|---|
| I | 重要程度，0–10 |
| W / P | 已等待時間／可等待耐久度，秒 |
| R | 棄單風險或損失係數，0–1；不是校準機率 |
| d | 起點至此訂單的 A* 距離，米 |
| v / v₀ | 節點附近速度上限／巡航速度，m/s |
| a、b | 左側「評分模式與權重係數」可調整 |

W 矩陣使用 `Wij = wj`（目的地重要度，對角線與終端點為 0）。每筆訂單的參數形成權重表，不需手動填滿 N×N 矩陣。新增／刪除訂單後下次規劃會重建矩陣。

預設營運目標：

$$L=T_{finish}+\lambda\frac{\sum_jw_jA_j}{\sum_jw_j}+\mu\sum_jR_j\frac{\max(0,W_j+A_j-P_j)}{P_j}+\nu D_{total}$$

包含完成時間、重要訂單等待、逾時損失與距離；每站服務時間也納入後續抵達時間。耐久度是軟目標，禁止順位是硬約束。詳見 [演算法與揭露書對照](docs/algorithm.md)，包含原始 sigmoid 公式、單位、Sower 實作與限制。

## SAW / Sower 多世界

開啟時維持多個獨立族群，定期收割菁英、洗牌並分配給其他世界，取代較差候選，同時保留各世界最佳。關閉時只跑單世界 GA。可調世界數、族群、世代、交換間隔、遷移比例、突變率與 seed。

- 「平行世界」是演算法族群，背景執行緒按世代輪流推進，不是多核心平行計算。
- 改善百分比相對於輸入順序（必要時修復順位限制）的 loss，不表示接近全域最優的比例。
- GA 不保證全域最優；Sower 使用較多候選評估，不能據此宣稱所有問題都優於單世界。
- 互動上限 30 訂單、8 世界、300 世代、每世界 200 族群，且總候選預算 ≤ 300,000。
- 本版處理單機器人、單樓層、固定訂單集合；不包含電梯、多車、動態行人或硬時限。

## 專案結構

```text
app.py                     本機 HTTP 入口與靜態檔案
scheduler/core.py          A*、矩陣、權重、目標函數、PMX、Sower
scheduler/api.py           輸入驗證、背景工作、取消與進度
web/                       繁中 Canvas Web UI，無 CDN
data/map/                 飯店／餐廳／倉儲 PNG 與預設節點
scripts/generate_maps.py    重建合成範例地圖
notebook/                  原始教學 notebooks 與新版實作教學
docs/algorithm.md          揭露書與實作公式對照
tests/                     演算法／HTTP／UI 測試
project_demo*/             原始 Python demo 與研究輸出（歷史參考）
```

## 教學 Notebook

```bash
pip install -r requirements-notebook.txt
jupyter lab notebook
```

先看 `notebook/costmap_sower_tutorial.ipynb`；兩本原始 `.ipynb` 已移入 `notebook/`，保留內容並加入目錄初始化與歷史限制說明。舊 Python demo 保留作研究對照，新 Web UI 完全使用 `scheduler/`。

## 驗證

```bash
python -m unittest discover -s tests -v
```

包含最短成本比對、牆角、膨脹、斷路、PMX、衝突限制、Sower、可重現性、小訂單數與 HTTP 端到端流程。另提供選用瀏覽器互動驗證：

```bash
npm install --no-save --package-lock=false playwright
npx playwright install chromium
python app.py
# 另一個終端機
node tests/browser-smoke.cjs
```

Web UI 本身不依賴 npm；以上僅用於開發驗證。瀏覽器測試會輸出截圖至被 gitignore 排除的 `test-artifacts/`。

## 常見問題

- **門口不可達**：檢查 m/px、半徑與門寬；保守膨脹後狹窄門可能關閉。不要為得到路線而任意縮小真實機器人半徑。
- **等很久**：先降低世代／族群；A* 成本隨地圖與節點數增加，先試內建地圖。
- **順位無解**：若多筆訂單都被禁止占用所有可用順位，需修正條件。例如唯一一筆訂單不能禁止第 1 位。
- **想重現**：匯出完整訂單 JSON，之後匯入；會保留地圖、節點、參數與 seed。結果 JSON 額外包含完整歷史與矩陣。
- **埠已被占用**：使用 `python app.py --port 8001`。

原始授權見 [LICENSE](LICENSE)。
