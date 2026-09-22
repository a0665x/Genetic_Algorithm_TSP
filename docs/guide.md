# Usage and configuration

[Back to the overview](../README.md)

## Installation

The README covers Conda. For Python 3.11+ with pip:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8000. The application needs no GPU, frontend build, npm, external CDN, or cloud service. It is an unauthenticated local simulator; keep the default loopback binding and do not expose it directly to the public internet. Use `python app.py --port 8001` when the default port is occupied.

For an existing Conda installation:

```bash
git pull origin main
conda env update -f environment.yml --prune
conda activate dispatch-lab
python app.py
```

The main interface is Multi-floor Studio. The original single-floor interface remains at `/legacy`.

## Orders and results

Select a floor and an order to edit it. Click an empty traversable location to add an order, or use the Add control. Move order can relocate a selected order to another floor. Delete removes the selected order.

Importance, Already waited, and Patience are the primary controls. Waiting and patience are displayed in minutes and converted to seconds for calculation. **Patience is the total desired waiting window from order creation**, not the remaining time. Risk, local speed, service time, and forbidden visit positions are under More conditions. The interface currently uses Traditional Chinese labels.

Run the planner to see the selected route, arrival schedule, and objective components. Changing inputs clears the previous result. Switch between the editable top-down view and the stacked building view, or replay generations and compare worlds. Import/export preserves the scene for reuse.

Calculation details contains W/D/T matrices. Select a matrix cell to inspect its walking and elevator segments. Formulas and substitutions shows the equations and actual feature contributions. Settings groups map uploads, scale, elevators, scoring coefficients, and GA controls. A score coefficient of zero disables that feature's contribution.

## Maps and elevators

The included example has two synthetic 192 × 160 floor grids, six orders, and three elevator connections. These are reproducible occupancy fixtures, not measured LiDAR or a reconstruction of a perspective rendering.

Each floor has its own meters-per-pixel resolution. Upload separate top-down PNG, JPEG, PGM, or BMP images, 4–512 px per side and up to 2 MB per image. Images are never silently resized because resizing can remove thin walls. Maximums are four floors, 524,288 total cells, 12 elevator connections, 30 orders, and a 12 MB scene request.

Grayscale values at or below the obstacle threshold are blocked. White and gray cells above it are traversable; gray adds cost. Transparent pixels are composited onto black. A per-floor `unknown_value` can explicitly block one unknown grayscale value. Walls and map boundaries are conservatively inflated by `ceil(radius/resolution)` cells using a square kernel. Eight-neighbor A* does not cut blocked diagonal corners.

Elevators have explicit `(floor, x, y)` endpoints, availability, and forward/reverse waiting, door-cycle, and ride times. Connections are bidirectional, but their times may differ by direction. Floor overlap and drawn elevator shafts do not create connections. A perspective illustration must not be used as a single walkable occupancy grid.

## Scoring and scope

The scheduler combines completion time, priority-weighted arrival time, lateness/risk, and horizontal walking distance. The sigmoid priorities are fixed for each planning snapshot. Earlier service times contribute to subsequent arrivals; completion includes the last service and any requested terminal leg. See the [mathematical model](math_model.md) for equations, units, and historical comparisons.

W is a destination-priority view, not a physical edge cost. Same-floor candidates come from gray-cost A*. The directed portal graph selects minimum travel time over these precomputed candidates. T includes walking and elevator time. D is the horizontal walking distance on that same selected path, excluding elevator height. **Both D and T may be asymmetric** when opposite directions choose different elevators. This is not a globally fastest search over every possible continuous-speed-field path.

The simulator supports one robot, static orders, and static obstacles. Patience is a soft objective, not a guaranteed deadline. Risk is an input consequence coefficient, not a calibrated cancellation probability. Elevator waits are fixed estimates, not queue predictions. Elevator capacity, live pedestrians, multi-robot conflict resolution, ROS origin/rotation, and live SLAM ingestion are not implemented. Every terminal pair must be reachable; disconnected orders fail the job rather than being silently dropped.

Sower worlds are separate populations advanced on one background thread, not CPU-core parallelism. GA is a heuristic and does not guarantee a global optimum. Improvement compares against the feasible input-order baseline, not an optimality bound or an equal-compute benchmark. The candidate budget is `population × (generations + 1) × effective_worlds <= 300,000`.

## Development

Run the backend and HTTP regression suite:

```bash
python -m unittest discover -s tests -v
```

Optional browser integration checks start their own loopback server:

```bash
pip install playwright
python -m playwright install chromium
python tests/browser_studio.py
```

On hosts that prohibit browser navigation, an explicit harness is available:

```bash
python tests/browser_studio.py --offline-harness --chromium /usr/bin/chromium
```

The harness loads the same HTML/CSS/JS into an isolated DOM and bridges API calls to the real local HTTP server. It checks DOM/Canvas and backend interactions, not native browser networking or CSP enforcement. Reports and screenshots go to ignored `test-artifacts/`. The Node-based `tests/browser-smoke.cjs` targets `/legacy`.

### Rebuild the README animation

After generating the browser screenshots above:

```bash
python scripts/make_readme_demo.py
```

This combines `studio-plan.png`, `studio-building.png`, and `studio-math.png` into `docs/assets/dispatch-demo.gif`. It adds step headings and a settings highlight without changing displayed values or paths. It is a screenshot walkthrough, not continuous screen recording. The current demo uses the captured Studio validation screens from commit `2ad49c47481eb4683d321e9dd7be766eb389dcef`. The animation uses four steps over 15 seconds and loops without external hosting.

### Source layout

```text
app.py                    local HTTP server
scheduler/core.py         Costmap, sigmoid weights, objective, PMX, Sower
scheduler/building.py     multi-floor validation and portal graph
scheduler/api.py          job orchestration and legacy API
web/studio.{html,js,css}   Multi-floor Studio
scripts/export_studio.py  export synthetic floor maps and scene JSON
scripts/make_readme_demo.py  build the screenshot walkthrough
notebook/, project_demo*/ original research and teaching material
```

[Archived single-floor notes](algorithm.md) describe the legacy implementation, not the current portal layer.
