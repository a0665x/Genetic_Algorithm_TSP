from util.TSP_GA import create_locations ,GeneticAlgo,Location
from util.APF_PATH import APF , Vector2d , plot_obs_n_start_n_goal
from matplotlib import pyplot as plt
import time

if __name__ == '__main__':
    xs =      [  0,  50, 20 , 18,   35,  90,  40,  84,  74,  34,  20,  60,  74,  60, 50 ,  100]
    ys =      [  0,  62, 90 ,  0,   25,  89,  71,   7,  29,  45,  65,  69,  47,  40, 10 ,  100]
    cities  = ['A', 'P', 'B', 'C', 'K', 'O', 'Y', 'N', 'X', 'G', 'Q', 'S', 'J', 'L', 'W',  'Z']
    weights = [ 0 , 10 ,  4 ,  0 ,  8 ,  0 , 0.0,   0,   2,  10,  10,   0,   2,   0,   0,   0 ]#0~10

    locations = []
    for x, y, name,w in zip(xs, ys, cities,weights):
        locations.append(Location(name, x, y,w,Distance_Method='Weight_distence'))  # 距離算法: 'Euclidean' , 'Manhattan' , 'Minkowski' , 'Weight_distence'
    t1 = time.time()
    print('init_info:',locations,len(locations))
    #GeneticAlgo(路徑初始化,進化次數,總人口數,每次交配的點數,突變的機率,菁英佔總人口數的幾趴, 總共有幾個平行宇宙)
    my_algo = GeneticAlgo(locations, level=20, populations=150, variant=3, mutate_percent=0.15, elite_save_percent=0.4 , world_num=1)

    best_route, best_route_length = my_algo.evolution(xs, ys , cities , evo_jpg_save= True ,prohibit_filter_mode = False,prohibit_node=['C'], prohibit_idxs=[1,2,3])


    t2 = time.time()

    print('最終進化路徑/長度/計算耗時:', [loc.name for loc in best_route], best_route_length , f'{t2-t1}sec')
    print('最佳化路徑座標   :',[(loc.loc[0], loc.loc[1]) for loc in best_route])
    filally_xy = [(loc.loc[0], loc.loc[1]) for loc in best_route]
    # ========================================= APF ======================================
    is_plot = True
    rr = 10
    start = filally_xy[0]
    goal  = filally_xy[-1]

    subplot, obs = plot_obs_n_start_n_goal(obs_num=200, start=start, goal=goal, citys=list(zip(xs,ys)) , obs_radius = rr,map_size =100 ,is_plot=is_plot)

    Best_Total_Length = 0
    if subplot != 'no_plot_mode':
        for idx,city_loc in enumerate(best_route):

            k_att, k_rep = 1.0, 1.5   # 引力 / 斥力

            step_size, max_iters, goal_threashold = 1.0, 100, 0.5  # 1.0, 100, .5
            step_size_ = 5


            if idx !=0 or idx!=len(best_route)-1 :
                subplot.plot(city_loc.loc[0] , city_loc.loc[1] , 'X',markersize=12, color='red')
                subplot.text(city_loc.loc[0]+1 , city_loc.loc[1]+1 , city_loc.name+f'({city_loc.weight})')
            if idx>=1:
                apf = APF(best_route[idx-1].loc , city_loc.loc , obs , k_att , k_rep, rr, step_size, max_iters, goal_threashold, is_plot)
                apf.path_plan(subplot,is_plot)

                if apf.is_path_plan_success == True:
                    path = apf.path
                    path_ = []
                    i = int(step_size_ / step_size)
                    while (i < len(path)):
                        path_.append(path[i])
                        i += int(step_size_ / step_size)

                    if path_[-1] != path[-1]:
                        path_.append(path[-1])
                    path_length = apf.path_length(path_, start=best_route[idx-1].loc, goal=city_loc.loc)
                    # print(f'planed points len:{len(path_)},length:{path_length}')
                    # print('APF partial path:', path_)
                    # print('path plan success')

                    px, py = [K[0] for K in path_] , [K[1] for K in path_]
                    subplot.plot(px, py, '^',markersize=4, color='black')
                    Best_Total_Length +=path_length
                n = 1
                # 自適應場參數遞減, 嘗試防止斷線
                while apf.is_path_plan_success == False:

                    k_att_T, k_rep_T , goal_threashold_T,rr_T = round(k_att*0.8,2) , round(k_rep*0.8,4) , round(goal_threashold*0.8,4) ,round(rr*0.8,4)
                    print(f'路線{best_route[idx - 1].name}到{city_loc.name}斷線,第{n}次嘗試,嘗試前修改參數為:(k_att:{k_att_T}, k_rep:{k_rep_T} ,goal_threashold:{goal_threashold_T},rr:{rr_T})')
                    apf = APF(best_route[idx - 1].loc, city_loc.loc, obs, k_att_T, k_rep_T, rr_T, step_size, max_iters, goal_threashold_T, is_plot)
                    apf.path_plan(subplot, is_plot)
                    ########################################
                    path = apf.path
                    path_ = []
                    i = int(step_size_ / step_size)
                    while (i < len(path)):
                        path_.append(path[i])
                        i += int(step_size_ / step_size)

                    if path_[-1] != path[-1]:
                        path_.append(path[-1])

                    # print(f'planed points len:{len(path_)},length:{path_length}')
                    # print('path plan success')
                    px, py = [K[0] for K in path_], [K[1] for K in path_]
                    subplot.plot(px, py, '^',markersize=4, color='red')

                    #######################################
                    k_att, k_rep, goal_threashold , rr = round(k_att_T , 2), round(k_rep_T , 2), round(goal_threashold_T , 2) , round(rr_T,2)
                    n +=1
                    if n>=10:
                        print('自適應引斥力無法修正斷線問題')
                        break



        plt.title(f'best route:{[path.name for path in best_route]}\n total length:{round(Best_Total_Length,2)}(ground_true ~685)')
        plt.show()
    else:
        path_ = []
        for idx, city_loc in enumerate(best_route):
            if idx>=1 :
                apf = APF(best_route[idx-1].loc , city_loc.loc , obs , k_att , k_rep, rr, step_size, max_iters, goal_threashold, is_plot)
                apf.path_plan(subplot,is_plot)
                if apf.is_path_plan_success:
                    path = apf.path
                    i = int(step_size_ / step_size)
                    while (i < len(path)):
                        path_.append(path[i])
                        i += int(step_size_ / step_size)

                    if path_[-1] != path[-1]:
                        path_.append(path[-1])
                    path_length = apf.path_length(path_, start=best_route[idx-1].loc, goal=city_loc.loc)

                    print(f'planed points len:{len(path_)},length:{path_length}')

                    Best_Total_Length +=path_length
        print('APF total path:', path_)
        print('APF total length:',Best_Total_Length)
