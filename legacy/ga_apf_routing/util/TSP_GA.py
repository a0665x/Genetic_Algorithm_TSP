import random as rd
import copy
from matplotlib import pyplot as plt
import random
import math
import os
import glob
from PIL import Image
import numpy as np

def prohibit_filter(routes , prohibit_node = ['C','W']  , prohibit_idxs = [1,2, 3]):
    filter_routes = []
    for route in routes:
        true_append = True
        name_list = [r.name for r in route.path]
        prohibit_city = filter(lambda x: name_list.index(x) in prohibit_idxs, name_list)

        for node in prohibit_node:
            if node in prohibit_city:
                # print('路徑生成含有禁止路徑')
                true_append = False
        if true_append == True:
            filter_routes.append(route)
    return filter_routes


def make_gif(frame_folder):
    frames = [Image.open(image) for image in glob.glob(f"{frame_folder}/*.jpg")]
    frame_one = frames[0]
    frame_one.save(f"{frame_folder}.gif", format="GIF", append_images=frames,
               save_all=True, duration=100, loop=0)



class Location:
    def __init__(self, name, x, y,w,Distance_Method='Euclidean'):
        self.name = name
        self.loc = (x, y)
        self.weight = w
        self.Distance_Method = Distance_Method


    def sigmoid(self, x):
        return 1 / (1 + math.exp(-x))

    def distance_between(self, location2, **kwargs):  # Euclidean  Manhattan
        assert isinstance(location2, Location)
        if self.Distance_Method == 'Euclidean':
            #             print(f'從{location2.name}到{self.name}的距離:',((self.loc[0] - location2.loc[0]) ** 2 + (self.loc[1] - location2.loc[1]) ** 2) ** (1 / 2))
            return ((self.loc[0] - location2.loc[0]) ** 2 + (self.loc[1] - location2.loc[1]) ** 2) ** (1 / 2)
        elif self.Distance_Method == 'Manhattan':
            return (self.loc[0] - location2.loc[0]) + (self.loc[1] - location2.loc[1])
        elif self.Distance_Method == 'Minkowski':
            p = 3
            return ((self.loc[0] - location2.loc[0]) ** p + (self.loc[1] - location2.loc[1]) ** p) ** (1 / p)
        elif self.Distance_Method == 'Weight_distence':
            eucl_d = ((self.loc[0] - location2.loc[0]) ** 2 + (self.loc[1] - location2.loc[1]) ** 2) ** (1 / 2)
            key, que = list(kwargs.items())[0]
            # x = eucl_d / (10 * (self.weight + location2.weight + 1))
            # loss_d = abs(self.sigmoid(x/que))
            x = eucl_d / (10 * (self.sigmoid((self.weight + location2.weight)/5) + 1))
            loss_d = abs(x / que)
            # loss_d = abs(x / que)
            # print('loss_d:',loss_d)
            return loss_d


def create_locations():
    locations = []
    xs = [8, 50, 18, 35, 90, 40, 84, 74, 34, 40, 60, 74, 60, 50]
    ys = [3, 62, 0, 25, 89, 71, 7, 29, 45, 65, 69, 47, 40, 10]
    cities = ['Z', 'P', 'A', 'K', 'O', 'Y', 'N', 'X', 'G', 'Q', 'S', 'J', 'L', 'W']
    for x, y, name,w in zip(xs, ys, cities,weights):
        locations.append(Location(name, x, y , w,Distance_Method='Euclidean'))
    return locations, xs, ys, cities,weights


# 設計調用Route, 即賦予當下這個路徑path 可以計算出長度
class Route:
    def __init__(self, path):  # path: [Z_oc ,A_oc , D_oc , Q_oc ……]
        # path is a list of Location obj
        self.path = path
        self.length = self._set_length()

    def _set_length(self):
        total_length = 0
        path_copy = self.path[:]
        from_here = path_copy.pop(0)
        #         print('第一個位置開始計算:',from_here.name)
        init_node = copy.deepcopy(from_here)
        #         print('第一個位置開始計算:',init_node.name)
        que = 1
        while path_copy:
            to_there = path_copy.pop(0)
            #             print('to_there:',to_there.name)
            total_length += to_there.distance_between(from_here,idx = que)
            from_here = copy.deepcopy(to_there)
            que += 1
        #         total_length += from_here.distance_between(init_node , Distance_Method = 'Euclidean')
        #         print(f'=========這個路徑總長度:{total_length}===========')
        return total_length


class GeneticAlgo:
    def __init__(self, locs, level=10, populations=100, variant=3, mutate_percent=0.1, elite_save_percent=0.1 , world_num=1, sower_rate =0.5 ):
        self.locs = locs
        self.level = level
        self.variant = variant
        self.populations = populations  # populations 表示路徑群數量( 等同代碼為:len(routes) )
        self.mutates = int(populations * mutate_percent)
        self.elite = int(populations * elite_save_percent)  # 預期要產出的菁英路徑群的挑選數量
        self.world_num = world_num
        self.sower_rate = sower_rate

    def _find_path(self):
        # locs is a list containing all the Location obj
        locs_copy = self.locs[1:-1]  # 起點終點保留,只對中間路徑隨機取樣  #! 若改為循環模式,locs_copy = self.locs[:]

        path = [self.locs[0]]  # ! 若改為循環模式,path =[]
        while locs_copy:  # 等同便歷locs 每個路徑
            to_there = locs_copy.pop(locs_copy.index(rd.choice(locs_copy)))
            #             print('to_there:',locs_copy.index(rd.choice(locs_copy)))
            path.append(to_there)
        #             print(path)
        #         print('===================')
        path.append(self.locs[-1])  # ! 若改為循環模式,此行刪除
        #         print([p.name for p in path])
        #         print('起點終點確認:',path[0].name , path[-1].name)
        return path

    def _init_routes(self):
        routes = []
        for _ in range(self.populations):
            path = self._find_path()
            routes.append(Route(path))
        #         print([l.name for l in [r.path for r in routes][14]])
        return routes

    def _get_next_route(self, routes):
        routes.sort(key=lambda x: x.length, reverse=False)  # 把每次群體(路徑包),做排序,
        elites = routes[:self.elite][:]  # 挑選菁英的路徑
        crossovers = self._crossover(elites)  # 把菁英丟去交配
        # print(f'認定是菁英的數量:{len(elites)},然後挑選父母,交配繁衍的人口數量:{len(crossovers)}')
        return crossovers[:] + elites  # 回傳

    def _crossover(self, elites):
        # Route is a class type
        normal_breeds = []
        mutate_ones = []
        # 確保整個種群的populations不變, 所以先對不突變的做事,然後再突變產生剩下的部分
        for _ in range(self.populations - self.mutates):
            # print('菁英的前四強:',elites[:4])
            father, mother = rd.choices(elites[:4], k=2)  # 從菁英挑兩個為父母

            # variant 為某段要交配的長度, 接下隨機取點,決定父親(一堆PATH點位座標順序)
            # 要從哪個idx 城市位置之後取variant量的路徑做交換
            index_start = rd.randrange(1, len(father.path) - self.variant - 2)
            # ! 若改為循環模式 index_start = rd.randrange(0, len(father.path) - self.variant - 1)

            # list of Location obj
            #
            father_gene = father.path[index_start: index_start + self.variant]  # 先擷取父親出要交換的那部分
            # print('交換片段長度:',len(father_gene))
            father_gene_names = [loc.name for loc in father_gene]  # 知道要被交換的城市名子
            # 因為要交換, 所以母親基因先替除父親基因取下的雜交片段(長度為:len(variant))
            mother_gene = [gene for gene in mother.path if gene.name not in father_gene_names]
            # 把上面已經替除雜交片段的母親基因,額外確定一個位置,這個位置安插交換的那部分(father_gene)
            mother_gene_cut = rd.randrange(1, len(mother_gene))
            # create new route path
            # 以母親基因藉由上述的交換, 生出一些含有父母親片段的下個世代
            next_route_path = mother_gene[:mother_gene_cut] + father_gene + \
                              mother_gene[mother_gene_cut:]

            next_route = Route(next_route_path)
            # add Route obj to normal_breeds
            normal_breeds.append(next_route)

            # for mutate purpose
            # 以父親基因當作突變案例
            copy_father = copy.deepcopy(father)
            # 從父親基因準備好位置
            idx = range(1, len(copy_father.path) - 1)
            # ! 若改為循環模式 idx = range(0 , len(copy_father.path))

            # 從這些位置挑兩個位置
            gene1, gene2 = rd.sample(idx, 2)
            # 突變 = 選兩個基因位置做交換
            copy_father.path[gene1], copy_father.path[gene2] = copy_father.path[gene2], copy_father.path[gene1]
            mutate_ones.append(copy_father)
        # 整個突變路徑包, 隨機取得(mutate_percent比例)要沿用下一代母群, 此突變數量為當初設定的突變比例相對的數量
        mutate_breeds = rd.choices(mutate_ones, k=self.mutates)
        # 把子代與突變數做結合, 當作最後繼續疊代的 populations
        return normal_breeds + mutate_breeds

    def evolution(self, xs, ys ,cities , evo_n_gif_save=[True,True] ,prohibit_filter_mode = False, **kwargs):
        Best_length = 1e10
        for w in range(self.world_num):
            routes = self._init_routes()
            #         fig2, ax2 = plt.subplots()
            world_sower = []
            for _ in range(self.level):  # 總共要進化幾次
                routes = self._get_next_route(routes)
                # 此人口數 len(routes) = populations *(1 + elite_save_percent)
                if prohibit_filter_mode == True:
                    (key1, v1),(key2, v2) = list(kwargs.items())
                    routes = prohibit_filter(routes, prohibit_node=v1, prohibit_idxs=v2)
                    for r in routes[0:5]:
                        print([p.name for p in r.path])
                if evo_n_gif_save[0] == True:

                    if not os.path.exists(f'./evoluation_saved/world_{w+1}'):
                        os.makedirs(f'./evoluation_saved/world_{w+1}')


                    routes.sort(key=lambda x: x.length)
                    # print(f'第{_}次進化,從{len(routes)}條路徑競爭的冠軍內容:', [p.name for p in routes[0].path])
                    # print(f'第{_}次進化,最優路徑總長度:', routes[0].length)
                    # print('=========================================================')
                    routes_temp = routes
                    best_route_temp, best_route_length_temp = routes_temp[0].path, routes_temp[0].length
                    fig, ax = plt.subplots()
                    ax.plot([loc.loc[0] for loc in best_route_temp], [loc.loc[1] for loc in best_route_temp], 'red',
                            linestyle='-', marker='')

                    ax.scatter(xs, ys)
                    # for i, txt in enumerate(cities):
                    #     ax.annotate(txt, (xs[i], ys[i]))
                    for loc in best_route_temp:
                        ax.annotate(f'{loc.name}({loc.weight})',loc.loc)


                    plt.savefig(f'./evoluation_saved/world_{w+1}/第{w+1}世界-第{_+1}次進化_總路徑長度{best_route_length_temp}.jpg')
                    plt.clf()
                    plt.close('all')

                    # 進化後, 排序一下
            routes.sort(key=lambda x: x.length)
            best_route_T,best_length_T =  routes[0].path, routes[0].length
            print(f'第{w + 1}世界最佳長度:{best_length_T},路徑順序:{[r.name for r in best_route_T]}')
            if evo_n_gif_save[1] == True:
                make_gif(f'./evoluation_saved/world_{w+1}')


            if best_length_T< Best_length:
                Final_best_route = best_route_T
                Best_length = best_length_T
                print(f'目前第{w+1}世界最佳解')
        return  Final_best_route , Best_length


        # return routes[0].path, routes[0].length




