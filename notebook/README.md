# 教學 Notebooks

從 repo 根目錄執行：

```bash
conda activate dispatch-lab
pip install -r requirements-notebook.txt
jupyter lab notebook
```

- `dispatch_lab_demo.ipynb`：現行引擎的精簡端到端 demo；載入範例地圖、建立訂單、執行 A* + GA，並畫出路徑與收斂曲線。
- `costmap_sower_tutorial.ipynb`：較完整的演算法教學。從灰階地圖、A* 矩陣、sigmoid 權重、PMX、Sower 到進化曲線與配送路徑。
- `project_main.ipynb`：原始 GA/APF 研究筆記，內容與舊輸出保留，新增相對路徑初始化及歷史限制說明。
- `imgs2gif.ipynb`：原始進化影格轉 GIF 筆記，依賴既有 `legacy/ga_apf_routing/evoluation_saved`。

舊版程式集中在 `legacy/`，僅供歷史教學；其內嵌演算法不是 `scheduler/core.py` 的新版引擎。Notebook 第一個設定 cell 會定位專案根目錄，因此從根目錄或 notebook 目錄啟動均可。歷史兩本會把工作目錄切到舊 demo 路徑，以維持舊圖片引用。
