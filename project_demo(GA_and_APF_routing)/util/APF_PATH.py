from typing import Union
import math
from matplotlib import pyplot as plt
import random
from matplotlib.patches import Circle
import numpy as np



class Vector2d():
    def __init__(self, x, y):
        self.deltaX = x
        self.deltaY = y
        self.length = -1
        self.direction = [0, 0]
        self.vector2d_share()

    def vector2d_share(self):
        if type(self.deltaX) == type(list()) and type(self.deltaY) == type(list()):
            deltaX, deltaY = self.deltaX, self.deltaY
            self.deltaX = deltaY[0] - deltaX[0]
            self.deltaY = deltaY[1] - deltaX[1]
            self.length = math.sqrt(self.deltaX ** 2 + self.deltaY ** 2) * 1.0
            if self.length > 0:
                self.direction = [self.deltaX / self.length, self.deltaY / self.length]
            else:
                self.direction = None

        else:
            self.length = math.sqrt(self.deltaX ** 2 + self.deltaY ** 2) * 1.0
            if self.length > 0:
                self.direction = [self.deltaX / self.length, self.deltaY / self.length]
            else:
                self.direction = None


    def __add__(self, other):
        vec = Vector2d(self.deltaX, self.deltaY)
        vec.deltaX += other.deltaX
        vec.deltaY += other.deltaY
        vec.vector2d_share()
        return vec

    def __sub__(self, other):
        vec = Vector2d(self.deltaX, self.deltaY)
        vec.deltaX -= other.deltaX
        vec.deltaY -= other.deltaY
        vec.vector2d_share()
        return vec

    def __mul__(self, other):
        vec = Vector2d(self.deltaX, self.deltaY)
        vec.deltaX *= other
        vec.deltaY *= other
        vec.vector2d_share()
        return vec

    def __truediv__(self, other):
        return self.__mul__(1.0 / other)

    def __repr__(self):
        return 'Vector deltaX:{}, deltaY:{}, length:{}, direction:{}'.format(self.deltaX, self.deltaY, self.length,
                                                                             self.direction)


class APF():
    def __init__(self, start: (None), goal: (None), obstacles: Union[None, None], k_att: float, k_rep: float, rr: float,
                 step_size: float, max_iters: int, goal_threshold: float, is_plot=False, sigma=1):
        self.start = Vector2d(start[0], start[1])
        self.current_pos = Vector2d(start[0], start[1])
        self.goal = Vector2d(goal[0], goal[1])
        self.obstacles = [Vector2d(OB[0], OB[1]) for OB in obstacles]
        self.k_att = k_att
        self.k_rep = k_rep
        self.rr = rr
        self.step_size = step_size
        self.max_iters = max_iters
        self.iters = 0
        self.goal_threashold = goal_threshold
        self.path = list()
        self.is_path_plan_success = False
        self.is_plot = is_plot
        self.delta_t = 0.01
        self._sigma = sigma

    def attractive(self):
        att = (self.goal - self.current_pos) * self.k_att
        # att = -(1/(self._sigma*math.sqrt(2*math.pi))) * math.exp(-((self.goal - self.current_pos)/(2*self._sigma*self._sigma)))
        return att

    def repulsion(self):
        rep = Vector2d(0, 0)
        for obstacle in self.obstacles:
            # obstacle = Vector2d(0, 0)
            obs_to_rob = self.current_pos - obstacle
            rob_to_goal = self.goal - self.current_pos
            if (obs_to_rob.length > self.rr):
                pass
            else:
                rep_1 = Vector2d(obs_to_rob.direction[0], obs_to_rob.direction[1]) * self.k_rep * (
                        1.0 / obs_to_rob.length - 1.0 / self.rr) / (obs_to_rob.length ** 2) * (rob_to_goal.length ** 2)
                rep_2 = Vector2d(rob_to_goal.direction[0], rob_to_goal.direction[1]) * self.k_rep * (
                            (1.0 / obs_to_rob.length - 1.0 / self.rr) ** 2) * rob_to_goal.length
                rep += (rep_1 + rep_2)
        return rep

    def path_plan(self,subplot,is_plot):
        while (self.iters < self.max_iters and (self.current_pos - self.goal).length > self.goal_threashold):
            potential_vec = self.attractive() + self.repulsion()
            self.current_pos += Vector2d(potential_vec.direction[0], potential_vec.direction[1]) * self.step_size
            self.iters += 1
            self.path.append([self.current_pos.deltaX, self.current_pos.deltaY])
            if is_plot==self.is_plot==True:
                subplot.plot(self.current_pos.deltaX, self.current_pos.deltaY, '.b')
                # plt.pause(self.delta_t)
        if (self.current_pos - self.goal).length <= self.goal_threashold:
            self.is_path_plan_success = True
            # print('短路徑點位:',len(self.path))

    def path_length(self, path_, start=[0, 0], goal=[30, 30]):
        def cal_distence(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

        length = 0

        path_.insert(0, start)
        path_.append(start)
        for idx, point in enumerate(path_):
            if idx >= 1:
                L = cal_distence(point, path_[idx - 1])
                length = length + L
        return length

def plot_obs_n_start_n_goal(obs_num =10, start = (0,0) ,goal = (30,30) ,citys = list ,obs_radius = float,map_size=int, is_plot = True):
    if is_plot:
        fig = plt.figure(figsize=(10,12))
        subplot = fig.add_subplot(111)
        subplot.set_xlabel('X-distance: m')
        subplot.set_ylabel('Y-distance: m')
        subplot.set_xlim(0-(map_size/10), map_size*1.1)
        subplot.set_ylim(0-(map_size/10), map_size*1.1)
        subplot.plot(start[0], start[1] ,'*r',markersize=12)
        subplot.plot(goal[0], goal[1], '*r',markersize=12)
        subplot.text(start[0]-1, start[1]-1 , 'Start')
        subplot.text(goal[0]-1, goal[1]-1, 'Goal')
    obs = []
    n = 1
    # print('obstacles: {0}'.format(obs))
    while len(obs)<=obs_num:
        save_obs = True
        random_obs = [round(random.uniform(2, map_size - 1),2), round(random.uniform(2, map_size - 1),2)]
        for city in citys:
            obs_city_dist = ((city[0]-random_obs[0])**2+(city[1]-random_obs[1])**2)**0.5
            if obs_city_dist < obs_radius*0.6:
                # print(f'{random_obs}離{city}距離({obs_city_dist})小於半徑{obs_radius}')
                save_obs = False
                break
        if save_obs == True:
            obs.append(random_obs)

    # print('obstacles: {0}'.format(obs))
    if is_plot:
        for OB in obs:
            circle = Circle(xy=(OB[0], OB[1]), radius=obs_radius, alpha=0.3)
            subplot.add_patch(circle)
            subplot.plot(OB[0], OB[1], 'xk')
        # print('all obs points:', obs)
        return subplot , obs
    else:
        return 'no_plot_mode', obs