# Genetic_Algorithm_TSP
### The first method (project_demo (GA_and_APF_routing)) uses a genetic algorithm and the theory of multi-universe evolution to select the best path in the universe and store it in the 'evoluation_saved' folder, and uses the APF algorithm to retrieve the graph.

##### Step 1:
##### cd project_demo (GA_and_APF_routing)
##### Step 2:
##### pip install -r requirements.txt
##### Step 3:
##### <<Modify the node parameters in mean.py, as follows>>
##### xs = [0, 50, 20, 18, 35, 90, 40, 84, 74, 34, 20, 60, 74, 60, 50, 100] (x-coordinates of the nodes)
##### ys = [0, 62, 90, 0, 25, 89, 71, 7, 29, 45, 65, 69, 47, 40, 10, 100] (y-coordinates of the nodes)
##### cities = ['A', 'P', 'B', 'C', 'K', 'O', 'Y', 'N', 'X', 'G', 'Q', 'S', 'J', 'L', 'W', 'Z'] (node code)
##### weights = [0, 10, 4, 0, 8, 0, 0.0, 0, 2, 10, 10, 0, 2, 0, 0, 0] (node weights: the higher the weight, the earlier the node needs to be arranged)
##### Note: The node code in the above example will be considered the first 'A' as the starting point, 'Z' as the endpoint, and the combination of the middle part will be the optimization core of this algorithm. Therefore, as long as the user focuses on writing all the points correctly, and pays attention to the starting and ending points, they can execute this algorithm.
##### Step 4:
##### python mean.py
##### Step 5:
##### Check the evoluation_saved folder to view the evolution process and confirm the final route.
![world_4](https://user-images.githubusercontent.com/44718189/215989553-92c4cdce-c7b6-4c56-9bb4-6fe1c71d3a0d.gif)
### The second method (project_demo (weight_table_routing)) uses a time table and a weight table (json_time_table and json_weight_table in the code), and the evolution process will be based on table look-up as the genetic algorithm evolves. These tables are defined by the customer/user. If the two nodes cannot be directly connected, it will be NaN, and in the evolution process, the length of the route cannot be calculated for sorting the elite route, so it will automatically exclude the nodes that cannot be connected as the basis of the routing algorithm.

##### Step 1:
##### Edit the json_time_table and json_weight_table, and modify line 27 of GA_Table_Path_Plaining.py.
##### Step 2:
##### Set the parameters => GeneticAlgo (route initialization, evolution times, total population, number of points per mating, mutation probability, elite population percentage, total number of parallel universes).
##### python GA_Table_Path_Plaining.py


