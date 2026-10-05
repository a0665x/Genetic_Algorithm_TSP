from util.GA_Function import make_nodes_dataframe , check_table , Location_mapping , Route , GeneticAlgo
import time
import json
import pandas as pd
import numpy as np
import os
import copy
def fake_table_generator(orders , customized_nan={'A': 'C', 'B': 'G', 'J': 'C' , "K":'A' , "A":'K' , "K":'B' , "B":'K' , "A":'G' , "G":'A' , "F":'G' , "G":'F' , "B":'A' , "A":'B'}):
    time_maps = make_nodes_dataframe(nodes_list=orders, nide_num=len(orders), max_time=60,
                                     customized_nan=customized_nan)
    # make fake order time table
    df_time_table = pd.DataFrame(time_maps, columns=orders, index=orders)
    print('time_table \n', df_time_table)
    t_result = df_time_table.to_json(orient="split")
    json_time_table = json.loads(t_result)
    # ============================================
    # make fake order weight table
    df_weight_table = pd.DataFrame(np.ones((len(orders), len(orders))), columns=orders, index=orders)
    print('weight_table \n', df_weight_table)
    w_result = df_weight_table.to_json(orient="split")
    json_weight_table = json.loads(w_result)
    return json_time_table , json_weight_table

if __name__ == "__main__":
    # orders = ['A', 'P', 'B', 'C', 'K', 'O', 'Y', 'N', 'X', 'G', 'Q', 'S', 'J', 'L', 'W',  'Z']
    orders = ['A' , 'C', 'K' , 'B', 'J', 'G' ,  'Z']   #{'A': 'C', 'B': 'G', 'J': 'C'}
    json_time_table , json_weight_table = fake_table_generator(orders , customized_nan={ "K":'A' , "A":'K' , "K":'B' , "B":'K' , "A":'G' , "G":'A'  , "G":'A' , "B":'A' , "A":'B'})
    print(json_time_table)

    locations = []
    for idx, n in enumerate(orders):
        locations.append(Location_mapping(n , json_time_table, json_weight_table , Distance_Method = 'consider_weight_table'))

    t1 = time.time()
    # GeneticAlgo(路徑初始化,進化次數,總人口數,每次交配的點數,突變的機率,菁英佔總人口數的幾趴, 總共有幾個平行宇宙)
    my_algo = GeneticAlgo(locations, level=20, populations=100, variant=3, mutate_percent=0.15, elite_save_percent=0.4,
                          world_num=20)
    # my_algo.evolution(初始順序,是否要存每個世界的jpg , 未完成的禁止過濾功能)
    best_route, best_route_length = my_algo.evolution(orders, evo_jpg_save=True , prohibit_filter_mode=False)

    t2 = time.time()

    print('最終進化路徑: {} \n長度:{} \n計算耗時:{}'.format(str([loc.name for loc in best_route]).replace("', '",'->'), best_route_length, f'{t2 - t1}sec'))


