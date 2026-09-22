# Genetic Algorithm TSP · Dispatch Lab

A local robot-dispatch simulator with **multi-floor occupancy grids, explicit elevator connections, A* routing, sigmoid order priorities, PMX genetic optimization, and Sower elite migration**.

The default UI is now the **Multi-floor Studio**. The original single-floor application remains available at `/legacy`; its API and historical demos are retained. The Studio is implemented in code, not a static design mockup.

## Run

```bash
git clone https://github.com/a0665x/Genetic_Algorithm_TSP.git
cd Genetic_Algorithm_TSP
conda env create -f environment.yml
conda activate dispatch-lab
python app.py
```

Open **http://127.0.0.1:8000**. Existing checkouts can run `git pull origin main` first. Alternatively, use Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The application needs no GPU, frontend build, npm, external CDN, or cloud service. It is an unauthenticated local simulation tool and binds to loopback by default. Do not expose it directly to the public internet.

## A simple operating workflow

1. Select a floor and click **Add** or an empty traversable location to create an order. Select an existing order to edit it. Use **Move order** to relocate it, including to another floor.
2. Edit **Importance**, **Already waited**, and **Patience**. The UI displays minutes for waiting/patience and converts to seconds in the API. Patience is the total desired waiting window from order creation, not remaining time. Risk, local speed, service time and forbidden visit positions are under **More conditions**.
3. Click **Plan**. The selected route, arrival schedule, actual priority and objective components come from the backend run snapshot. Changes to inputs invalidate the previous result.
4. Switch between the editable top-down floor view and the stacked building view. The latter visualizes the same grids and portal links; it is not an image fed back into A*.
5. Open **Calculation details** to inspect W/D/T matrices. Click a matrix cell to see its actual walking and elevator segments. Expand **Formulas and substitutions** for the model equations and numeric feature contributions.

Settings group floor uploads, map scale, elevators, score coefficients and GA controls behind a dialog. A score coefficient of zero disables that feature's contribution. The UI does not ask users to fill an N-by-N weight table manually.

## Maps and elevator topology

The built-in example contains **two 192 × 160 synthetic floor grids, six orders and three elevator connections**. These are reproducible occupancy fixtures, **not measured LiDAR data or a reconstruction of the supplied perspective render**. Doors have explicit openings; white and gray cells above the obstacle threshold are traversable, while black walls are blocked.

Each floor has its own meters-per-pixel resolution. Upload PNG, JPEG, PGM or BMP, 4–512 px per side, up to 2 MB per image. The Studio accepts at most four floors, 524,288 total cells, 12 elevator connections and 30 orders. Scene requests are bounded to 12 MB. It never silently resizes a map, since resizing can remove thin walls.

Transparent pixels are composited onto black. An optional per-floor `unknown_value` explicitly blocks an unknown grayscale value. Obstacles and map boundaries are conservatively inflated by `ceil(radius/resolution)` cells with a square kernel. Eight-neighbor A* cannot cut blocked diagonal corners.

Elevators have explicit endpoints `(floor, x, y)`, an enabled flag, forward/reverse waiting time, door-cycle time and ride time. No vertical connection is inferred from overlapping pixels or elevator artwork. In this version, each connection is bidirectional; its traversal times may differ by direction.

The original perspective image remains a **negative compatibility fixture**. Upload separate top-down grids instead of treating gray background, floor plates and drawn elevator shafts as a single walkable image.

## What is actually optimized?

For each order, the existing model computes:

$$
z_j=b+a_I I_j/10+a_W\min(E_j/\tau_j,3)+a_RR_j+a_D\min(D_{0j}/50\mathrm{m},3)+a_V(1-\min(v_j,v_0)/v_0)
$$

$$
\omega_j=1+9\sigma(z_j),\qquad\sigma(z)=\frac{1}{1+e^{-z}}.
$$

The priority matrix uses **row = source, column = destination**: `w_ij = omega_j` for order destinations off the diagonal; diagonal, START and END destination columns are zero. Thus, between order nodes, `w_ji = omega_i`.

The operational objective is unchanged:

$$
L(\pi)=T_{finish}+\lambda\frac{\sum_j\omega_j A_j}{\sum_j\omega_j}
+\mu\sum_j R_j\frac{\max(0,E_j+A_j-\tau_j)}{\tau_j}+\nu D_{total}.
$$

Defaults: lambda = 1, mu = 120 seconds and nu = 1 second/meter. Arrival times include earlier service times. Completion time includes the last service and any requested return/custom-end leg. Weights are fixed for a planning snapshot, not continuously recomputed during delivery.

**Multi-floor path selection:** same-floor walking segments come from gray-cost A*. A directed portal graph then selects minimum travel time among those precomputed segments. `T_ij` includes walking plus elevator time; `D_ij` is the **horizontal walking distance on that same selected path**, excluding elevator height. Unlike the legacy single-floor cached path matrix, **both D and T can be asymmetric** when opposite directions select different elevators. Neither matrix is a fabricated Euclidean shortcut.

See [the mathematical model](docs/math_model.md) for exact propagation from z to sigmoid to route loss, historical formula differences, and caveats.

## Scope and limits

This is a single-robot, static-order simulator. Patience is a soft objective, not a guaranteed hard deadline. Risk is an input consequence coefficient, not a calibrated cancellation probability. Elevator waits are fixed estimates, not queue predictions; elevator capacity, live pedestrians, multi-robot conflict resolution, ROS origin/rotation and live SLAM ingestion are not implemented.

The graph minimizes time over precomputed A* walking candidates, not the globally fastest path through an arbitrary continuous speed field. GA optimizes the permutation over those fixed matrices, not the joint choice of every possible geometric path. Every terminal pair must be reachable; a disconnected order fails the entire job rather than being silently dropped.

Sower worlds are separate populations on one background thread, not CPU-core parallelism. The GA does not guarantee a global optimum. Improvement percentages compare against the feasible input-order baseline, not an optimality bound or an equal-compute benchmark. Candidate budget: `population × (generations + 1) × effective_worlds <= 300,000`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers legacy behavior, rendered-map incompatibility, multi-floor continuity, obstacle/corner safety, elevator direction and availability, matrix sums, sigmoid sensitivity, arrival recursion, score decomposition, replay and HTTP snapshots.

Optional browser integration test (starts its own loopback HTTP server):

```bash
pip install playwright
python -m playwright install chromium
python tests/browser_studio.py
```

On hosts that prohibit browser navigation, the explicit offline harness loads the same HTML/CSS/JS into an isolated DOM and bridges API calls to the real local HTTP server:

```bash
python tests/browser_studio.py --offline-harness --chromium /usr/bin/chromium
```

This mode tests DOM/Canvas and backend interaction, **not browser networking or CSP enforcement**. Screenshots and a JSON report are written to ignored `test-artifacts/`. The original Node-based browser smoke test now targets `/legacy`.

## Structure

```text
app.py                     local server; Studio and legacy routes
scheduler/core.py          original Costmap, sigmoid weights, objective, PMX, Sower
scheduler/api.py           legacy validation and extensible job orchestration
scheduler/building.py      multi-floor validation, portal graph, explainable snapshots
web/studio.{html,js,css}    default progressive-disclosure UI
web/index.html             preserved single-floor UI at /legacy
scripts/export_studio.py   export synthetic floor PNGs and importable scene JSON
tests/test_building.py     multi-floor/math/HTTP regression tests
tests/browser_studio.py    browser and offline-harness interaction tests
docs/math_model.md         current model, units and historical comparison
notebook/, project_demo*/  original research and teaching material
```

For the archived single-floor implementation notes, see [docs/algorithm.md](docs/algorithm.md). Those notes describe the legacy implementation, not the new portal layer. License: [Apache 2.0](LICENSE).
