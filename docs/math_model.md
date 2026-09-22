# Mathematical model and implementation contract

The Multi-floor Studio uses `scheduler/building.py` as an adapter around the existing `scheduler/core.py` objective and GA. The legacy UI at `/legacy` retains the disclosure-comparison mode. The Studio uses operational scoring only.

## 1. Separate geometry, traversal time and urgency

Each floor has a grayscale grid, a resolution in meters/pixel and an inflated obstacle mask. A* minimizes

$$
C(P)=\sum_{(a,b)\in P}\Delta s_{ab}\frac{g(a)+g(b)}2,
\qquad g(p)=1+\gamma\frac{255-\operatorname{pixel}(p)}{255}.
$$

The obstacle mask is a hard constraint. Order importance never makes a blocked cell traversable. Transparent pixels and explicitly configured unknown cells are occupied. Inflation uses a conservative square footprint; diagonal moves require both orthogonal neighbors to be free.

Walking time integrates that selected path's weighted segment length divided by speed. As in the legacy approximation, the destination order's speed cap applies in its local Euclidean neighborhood on the final walking leg. Other walking legs use cruise speed. This is not a cell-level, globally fastest speed-field search.

An elevator connection has explicit floor-tagged endpoints:

$$
T_e^{a\to b}=t_{wait}^{a\to b}+t_{door}+t_{ride},\qquad
T_e^{b\to a}=t_{wait}^{b\to a}+t_{door}+t_{ride}.
$$

Enabled connections are bidirectional; forward/reverse waiting times can differ. Disabled connections contribute no graph edges. The portal graph can provide a detour through another floor when a same-floor walking pair is disconnected.

For each terminal pair, Dijkstra selects a minimum-time path **over the precomputed A* segment graph**:

$$
P_{ij}=\arg\min_{P\in\mathcal P_{ij}}\sum_{e\in P}T_e,\quad
T_{ij}=\sum_{e\in P_{ij}}T_e,\quad
D_{ij}=\sum_{e\in P_{ij},\ e\text{ is walking}}D_e.
$$

D measures horizontal walking distance only. It does not add elevator height or waiting time. Opposite directions may choose different elevators, so both D and T can be asymmetric. This differs from the legacy single-floor implementation, which caches one walking path and its reverse and therefore has symmetric D.

## 2. Order features to bounded priority

Use E for elapsed waiting time, avoiding confusion with the matrix W. For order j:

$$
z_j=b+a_I\frac{I_j}{10}+a_W\min\left(\frac{E_j}{\tau_j},3\right)
+a_RR_j+a_D\min\left(\frac{D_{0j}}{50\mathrm m},3\right)
+a_V\left(1-\frac{\min(v_j,v_0)}{v_0}\right).
$$

I is importance in [0,10]; E and patience tau are seconds; R in [0,1] is a user consequence coefficient; D is meters; speeds are m/s. The UI converts minutes to seconds at input boundaries. Patience means total time since order creation, not remaining patience.

Defaults `(aI,aW,aR,aD,aV,b) = (2,2,2,1,1,-3)` are unchanged. Setting a coefficient to zero disables its contribution. The five named features are configurable; arbitrary executable expressions and user-defined feature schemas are not supported.

$$
s_j=\sigma(z_j)=\frac1{1+e^{-z_j}},\qquad\omega_j=1+9s_j.
$$

Mathematically `1 < omega < 10`. The implementation clips sigmoid's argument to [-60,60] and floating-point saturation can yield an endpoint; the numerical range is [1,10]. The backend returns `features`, per-feature `contributions`, `bias`, `z`, `sigmoid` and `weight` from the actual run, not a second UI-side score calculation.

## 3. Directed destination-priority matrix

For N orders, START is index 0; order j is index j. An optional END follows the orders.

$$
w_{ij}=\begin{cases}\omega_j & i\ne j,\ 1\le j\le N,\\0 & \text{otherwise.}\end{cases}
$$

For distinct **order** nodes, `w_ij = omega_j` and `w_ji = omega_i`. The matrix is an explanatory destination-priority lookup, not a physical edge cost or an independent N-by-N set of tunable weights. The optimizer directly uses the same omega vector; it does not need to read the displayed W matrix as a separate computational stage.

## 4. Arrival recursion and operational loss

For a permutation pi:

$$
A_{\pi_1}=T_{0,\pi_1},\qquad
A_{\pi_k}=A_{\pi_{k-1}}+S_{\pi_{k-1}}+T_{\pi_{k-1},\pi_k}.
$$

S is service duration; A is arrival time, both seconds. The last service is included in completion time. A custom end overrides return-to-start; an open route adds no terminal travel leg.

$$
L(\pi)=T_{finish}
+\lambda\frac{\sum_j\omega_j A_j}{\sum_j\omega_j}
+\mu\sum_j R_j\frac{\max(0,E_j+A_j-\tau_j)}{\tau_j}
+\nu D_{total}.
$$

The denominator tau remains **inside each order's risk summand**. Defaults lambda=1 (dimensionless), mu=120 seconds and nu=1 second/meter give a seconds-equivalent loss. Risk is not a calibrated probability; patience is a soft objective. Hard constraints currently prohibit specified 1-based visit positions. The UI's four component numbers sum to the actual scored loss.

The exact sigmoid propagation is

$$
L_{priority}=\lambda\frac{\sum_j[1+9\sigma(z_j)]A_j}{\sum_j[1+9\sigma(z_j)]}.
$$

For fixed arrivals and unclipped z, with `bar A = sum(omega A)/sum(omega)`:

$$
\frac{\partial\bar A}{\partial z_j}
=\frac{9\sigma(z_j)[1-\sigma(z_j)]}{\sum_k\omega_k}(A_j-\bar A).
$$

This is a fixed-route sensitivity identity, not gradient descent. Outside the implementation's clipping interval, the derivative of the clipped implementation is zero. Changing order inputs can also change T/D or the risk term, so this partial derivative is not the total effect of every user-field change.

Weights are frozen for a run. The GA ranks permutations using the operational objective over fixed matrices. It does not jointly optimize every possible geometric path, elevator queue evolution or robot interaction.

## 5. Historical formulas are not the same objective

The original `Weight_distence` branch of `project_demo(GA_and_APF_routing)/util/TSP_GA.py` uses user-supplied endpoint weights h, not weights that originally came from the new feature model:

$$
C^{old}_{ij,k}=\frac{d_{ij}}{10k[1+\sigma((h_i+h_j)/5)]}.
$$

The legacy disclosure-comparison mode in the current core uses

$$
C^{disc}_{ij,k}=\sigma\left(\frac{d_{ij}}{10k(1+\omega_i+\omega_j)}\right).
$$

These are comparison scores, not seconds-equivalent operational losses. The numeric scales in historical expressions are legacy conventions, not physical constants. Division by visit position k may favor postponing expensive edges; neither expression guarantees urgent-first scheduling. The original disclosure document is not stored in this repository, so this note verifies the repository's implementation rather than independently authenticating the source document.

## 6. Reproducibility and observability

API metadata includes `model_version`, input coefficients/settings, W/D/T, floor-tagged walking/elevator segments and formulas. History contains the actual selected generation/world, schedule and component breakdown. Scene JSON preserves floor images, physical scale, node/portal parameters and seed. Importing or editing a scene invalidates old results.

`tests/test_building.py` verifies segment continuity, corner safety, elevator-only floor transitions, time/distance sums, reverse-direction route differences, loss decomposition, finite-difference sigmoid sensitivity and small enumerated reference problems. A small exact-reference test is not a claim of optimality on arbitrary instances.


## Ordered-node editor

The schema-3 adapter maps `nodes[0]` and `nodes[-1]` to fixed route terminals. Nodes in between are the orders optimized by the existing operational objective. Endpoint attributes do not enter the sigmoid weight normalization or order-service sum. Ordered A* previews compute only consecutive requested terminal pairs and never call `evolve`. Portal selection and units are identical to the full-matrix planner. The displayed preview duration is **travel only**; GA completion duration also includes intermediate service times.
