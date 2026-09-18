# Genetic Algorithm TSP · Robot Dispatch Lab

A local, interactive research/demo environment for converting robot delivery orders into a feasible service sequence. The current engine combines **occupancy-grid A*** routing, a **PMX permutation genetic algorithm**, and **Sower multi-world elite migration**, while keeping the original research demos and notebooks for comparison.

The main use case is indoor service robots (hotel, restaurant, warehouse) where route length alone is not enough: order importance, waiting time, patience, drop/cancellation risk, local speed limits, service time, and hard positional restrictions can all influence the schedule.

## Quick start

### Conda

```bash
git clone https://github.com/a0665x/Genetic_Algorithm_TSP.git
cd Genetic_Algorithm_TSP
conda env create -f environment.yml
conda activate dispatch-lab
python app.py
```

Open **http://127.0.0.1:8000**.

No GPU, Node.js, npm build, or external CDN is required for the application itself.

### Existing checkout

```bash
git pull origin main
conda env update -f environment.yml --prune
conda activate dispatch-lab
python app.py --port 8000
```

### Python venv

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

By default the server listens only on loopback. It is a local simulator, not an authenticated multi-user production service.

## What the current engine does

1. Load a built-in costmap or upload a grayscale map.
2. Place the robot start point and 1–30 order nodes.
3. Run A* between all relevant nodes to build distance and travel-time matrices.
4. Convert order attributes into bounded sigmoid priority weights.
5. Optimize the visit permutation with PMX crossover, mutation, elite retention, and optional Sower migration between worlds.
6. Replay generations and inspect route, ETA, lateness, distance, priority, and matrices.

If any required node is unreachable, or hard position constraints are inconsistent, the planner returns an error instead of drawing a straight line through an obstacle.

## Costmap semantics and A*

| Item | Current rule |
|---|---|
| Upload formats | PNG, JPG, PGM, BMP; max 2 MB |
| Dimensions | each side 4–512 px |
| Coordinates | top-left `(0,0)`, x right, y down |
| Obstacle threshold | grayscale `<= threshold` is blocked |
| White | `255`, lowest traversal cost |
| Gray | traversable above threshold, with extra cost |
| Transparent pixels | composited onto black, therefore occupied |
| Resolution | meters per pixel |
| Robot radius | conservatively inflated with a square kernel |
| Connectivity | 8-neighbor A*, no diagonal corner cutting |
| Unknown / multi-floor topology | not inferred automatically |

The A* edge cost between adjacent cells `a -> b` is

$$
c_{ab}=\Delta s_{ab}\frac{g(a)+g(b)}{2},
$$

where

$$
g(p)=1+\gamma\frac{255-I(p)}{255}\ge 1.
$$

`I(p)` is the grayscale value and `gamma` is `gray_cost`. The octile heuristic therefore remains admissible because the minimum traversal multiplier is 1.

## Priority model: from `z_j` to `sigmoid(z_j)` to the GA objective

The order-priority model is intentionally separated from the route geometry. For order `j`, define

$$
\begin{aligned}
z_j =\;& b
+a_I\frac{I_j}{10}
+a_W\min\left(\frac{E_j}{\tau_j},3\right)
+a_RR_j \\
&+a_D\min\left(\frac{d_{0j}}{50},3\right)
+a_V\left(1-\frac{\min(v_j,v_0)}{v_0}\right),
\end{aligned}
$$

then

$$
s_j=\sigma(z_j)=\frac{1}{1+e^{-z_j}},
$$

and the bounded node priority is

$$
\omega_j=1+9s_j=1+9\sigma(z_j), \qquad 1<\omega_j<10.
$$

The current defaults are

$$
(a_I,a_W,a_R,a_D,a_V,b)=(2,2,2,1,1,-3).
$$

Symbols:

| Symbol | Meaning |
|---|---|
| `I_j` | user importance score, 0–10 |
| `E_j` | seconds already waited before planning |
| `tau_j` | patience / desired arrival window in seconds |
| `R_j` | risk or consequence coefficient, 0–1; not a calibrated probability |
| `d_0j` | A* distance from the start node to order `j` |
| `v_j` | local speed limit near order `j` |
| `v_0` | cruise speed |

### Directed matrix notation `w_ij`, `w_ji`

The UI weight matrix is a **destination-priority matrix**, not a physical edge metric:

$$
w_{ij}=\omega_j,\qquad i\ne j.
$$

Therefore the reverse entry is

$$
w_{ji}=\omega_i,
$$

so in general

$$
w_{ij}\ne w_{ji}.
$$

This asymmetry is deliberate: the matrix says “how important is the destination of this transition?” rather than “what is the geometric cost of this edge?”. The geometric distance matrix `D_ij` remains symmetric, while travel time `T_ij` may be asymmetric because the destination-local speed limit is applied near the destination.

When a symmetric pair interaction is needed for the historical/disclosure expression, the implementation uses the pair coupling

$$
q_{ij}=1+\omega_i+\omega_j=q_{ji}.
$$

## How the sigmoid propagates into the operational loss

For a candidate visit order

$$
\pi=(\pi_1,\pi_2,\ldots,\pi_N),
$$

arrival times are recursive:

$$
A_{\pi_1}=T_{0,\pi_1},
$$

$$
A_{\pi_k}=A_{\pi_{k-1}}+S_{\pi_{k-1}}+T_{\pi_{k-1},\pi_k},\qquad k\ge2,
$$

where `S_j` is service time. If the route returns to start (or to a custom end), the finish time also includes the terminal travel leg.

The default operational objective is

$$
L(\pi)=T_{finish}
+\lambda\frac{\sum_j\omega_j A_j}{\sum_j\omega_j}
+\mu\sum_jR_j\frac{\max(0,E_j+A_j-\tau_j)}{\tau_j}
+\nu D_{total}.
$$

Substituting the sigmoid priority directly gives

$$
L_{priority}(\pi)
=\lambda
\frac{\sum_j\left[1+9\sigma(z_j)\right]A_j}
{\sum_j\left[1+9\sigma(z_j)\right]}.
$$

This is the exact downstream link from `z_j` to the GA score: `z_j` changes `sigma(z_j)`, which changes `omega_j`, which changes the weighted-arrival term used to rank whole permutations.

For a **fixed route** (important: the GA itself is not doing gradient descent),

$$
\frac{d\omega_j}{dz_j}=9\sigma(z_j)\left[1-\sigma(z_j)\right].
$$

If

$$
\bar A_\omega=\frac{\sum_k\omega_kA_k}{\sum_k\omega_k},
$$

then

$$
\frac{\partial \bar A_\omega}{\partial z_j}
=
\frac{9\sigma(z_j)(1-\sigma(z_j))}{\sum_k\omega_k}
\left(A_j-\bar A_\omega\right).
$$

Interpretation: the sigmoid has the greatest sensitivity near `z_j = 0`, saturates for very large positive/negative `z_j`, and changes the objective according to whether order `j` arrives later or earlier than the current weighted mean arrival time. The actual optimizer remains discrete because changing priorities can change the winning permutation itself.

Default objective coefficients are `lambda = 1`, `mu = 120 s`, and `nu = 1 s/m`, so the terms are approximately comparable as seconds-equivalent cost.

## Historical sigmoid vs. current operational model

There are three related but distinct formulas in the repository.

### 1. Historical Python demo

The old `TSP_GA.py` applies sigmoid to the *pair weight* inside a distance denominator:

$$
C^{old}_{ij,k}
=\frac{d_{ij}}
{10k\left[1+\sigma\left((\omega_i+\omega_j)/5\right)\right]}.
$$

Here `k` is the visit position. This is the behavior of the original demo code.

### 2. Disclosure-comparison mode

The current engine also keeps a comparison mode based on the disclosed expression:

$$
C^{disc}_{ij,k}
=\sigma\left(
\frac{d_{ij}}
{10k(1+\omega_i+\omega_j)}
\right).
$$

The total disclosure score is the sum of these edge terms.

### 3. Operational mode (default)

The default mode no longer hides importance inside a route-distance denominator. It first computes a stable, interpretable node priority `omega_j`, then uses that priority in weighted arrival, lateness/risk, finish time, and distance terms. This makes the contribution of each business variable visible in the UI and easier to tune.

## Sower / multi-world evolution

With Sower enabled, several independent GA populations are maintained. Every `interval` generations, elite routes are harvested, shuffled, and migrated into other worlds, replacing weak candidates while each world retains its own best solution.

Important limitations:

- “Worlds” are logical populations advanced by one background thread; this is not CPU-core parallelism.
- The GA is heuristic and does not guarantee a global optimum.
- Sower evaluates more candidates than single-world GA, so comparisons must control compute budget.
- Current scope is one robot, one 2D occupancy grid, static orders, and static obstacles.

## Test with the uploaded multi-floor LiDAR-style image

A downsampled fixture derived from the supplied two-floor image is included in the test suite as `tests/fixtures/lidar_multifloor_256.png.base64`.

The test confirms an important semantic conflict with the current planner:

1. The original image is `1672 x 941`, so it exceeds the current `512 px` side limit and must be preprocessed before upload.
2. After downsampling, the perspective background is around grayscale `193–196`. With the default obstacle threshold `100`, that background is interpreted as **free space**, even though it is not part of the floor occupancy grid.
3. Raising the threshold to around `200` blocks the background, but after the default `0.2 m` footprint inflation at `0.1 m/px`, only a very small fraction of the picture remains traversable. The rendered furniture, floor edges, elevator shafts, and perspective artifacts are not equivalent to a ROS occupancy grid.
4. The picture contains two floors and elevator/shaft graphics in one 2D image. A 2D A* planner cannot infer “same elevator, different floor” topology from those pixels. Multi-floor routing should be represented as separate floor costmaps plus explicit portal/elevator edges in a higher-level graph.

So this image is useful as a **negative/compatibility fixture**, but should not be treated as a production occupancy map without segmentation / rectification.

## Project structure

```text
app.py                     local HTTP entry point
scheduler/core.py          A*, matrices, priority model, objective, PMX, Sower
scheduler/api.py           validation, jobs, cancellation, progress
web/                       local Canvas UI
data/map/                  built-in synthetic occupancy maps
scripts/generate_maps.py   regenerate synthetic maps
notebook/                  teaching notebooks
docs/algorithm.md          implementation/disclosure notes
docs/math_model.md         detailed English mathematical derivation
tests/                     algorithm, HTTP, UI, and costmap compatibility tests
project_demo*/             original research/demo code retained for comparison
```

## Validation

```bash
python -m unittest discover -s tests -v
```

Optional browser smoke test:

```bash
npm install --no-save --package-lock=false playwright
npx playwright install chromium
python app.py
# another terminal
node tests/browser-smoke.cjs
```

The application itself does not depend on npm; Playwright is only for development validation.

## Common issues

- **Door becomes unreachable**: verify map resolution, robot radius, and door width. Conservative inflation can close narrow passages.
- **Uploaded map gives strange shortcuts**: inspect background grayscale and threshold. A rendered image is not automatically an occupancy grid.
- **Multi-floor map**: use one occupancy map per floor and connect floors with explicit elevator/portal edges; do not expect 2D A* to infer vertical topology.
- **Slow optimization**: reduce generations/population/worlds first; all-pairs A* preprocessing can also dominate on large maps.
- **Infeasible position constraints**: forbidden positions may eliminate every valid permutation.
- **Reproducibility**: keep the same map, orders, coefficients, settings, and seed.

See [LICENSE](LICENSE) for the project license.
