# Genetic_Algorithm_TSP
第一種方法(project_demo(GA_and_APF_routing)),是使用基因演算法,以及多重宇宙進化理論,選出最優的宇宙裡的最佳路徑,並且存在'evoluation_saved'資料夾中,並且以APF算法將圖存取出來.

## 步驟如下
##### 步驟1: 
##### cd project_demo(GA_and_APF_routing)
##### 步驟2: 
##### pip install -r requirements.txt
##### 步驟3:
##### <<修改mean.py節點參數,範例如下>>
##### xs      = [  0,  50, 20 , 18,   35,  90,  40,  84,  74,  34,  20,  60,  74,  60, 50 ,  100]  (結點的座標x) 
##### ys      = [  0,  62, 90 ,  0,   25,  89,  71,   7,  29,  45,  65,  69,  47,  40, 10 ,  100]  (結點的座標y) 
##### cities  = ['A', 'P', 'B', 'C', 'K', 'O', 'Y', 'N', 'X', 'G', 'Q', 'S', 'J', 'L', 'W',  'Z']  (結點代號)
##### weights = [ 0 , 10 ,  4 ,  0 ,  8 ,  0 , 0.0,   0,   2,  10,  10,   0,   2,   0,   0,   0 ]  (結點權重: 越高代該結點需要排列前面一點)
##### 注意: 以上範例的節點代號,會認定第一個'A'為起點,'Z'為終點,中間部分的排列組合就會是本算法的優化核心,因此使用者只要專注把所有點位寫好,必且注意開始與結束的結點,就可以執行本算法
##### 步驟4:
##### python mean.py
##### 步驟5:
##### 查看evoluation_saved資料夾,查看進化過程,確定最終的路線
![world_4](https://user-images.githubusercontent.com/44718189/215989553-92c4cdce-c7b6-4c56-9bb4-6fe1c71d3a0d.gif)


第二種方法(project_demo(weight_table_routing)),使用time table 以及 weight table 表(代碼中為:json_time_table , json_weight_table),使的進化過程,會以查表方式,作為基因算法進化的演化過程,這些表是由客戶/使用者自行定義,若該兩結點無法直通,就會是Nan,在演化過程中,就會無法計算路徑長度排序菁英路徑,因此會自動排除無法相通的結點作為路徑算法的依據
##### 步驟1:
##### 編輯json_time_table , json_weight_table,修改GA_Table_Path_Plaining.py的第27行
##### 步驟2:
##### 設定參數>>GeneticAlgo(路徑初始化,進化次數,總人口數,每次交配的點數,突變的機率,菁英佔總人口數的幾趴, 總共有幾個平行宇宙)
##### 步驟3:
##### python GA_Table_Path_Plaining.py

