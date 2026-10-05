# Usage guide

[Overview](../README.md) · [Mathematical model](math_model.md)

## Installation

For the containerized setup and lifecycle commands, use `./run.sh`; see the root README. The service is published only on `127.0.0.1` by default.

To run without Docker, use Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8000. Use `python app.py --port 8001` when the port is occupied. Keep the server on localhost; this local simulator does not provide authentication for public deployment.

## Start with one sheet

The homepage starts with one empty, synthetic sheet and no tasks or elevator connections. Choose **Upload map** to replace that unused starter with your own image. **+ Sheet** adds another map; batch selection reviews each image in sequence. The included populated example is available at `/?example=1`, not imposed on first launch.

The importer suggests pixel rules and shows the original beside the robot-clear preview. **Use this map** is the review confirmation; there is no second checkbox. Scale defaults to **0.1 m per source pixel, explicitly marked assumed**. Expand **Scale & classification options** when a calibrated scale or different pixel interpretation is needed. The app does not infer physical scale. Wall/unknown rules and clearance checks are unchanged. See [Map import](semantic_maps.md).

Drag a sheet's **⠿** grip to reorder it. The leftmost sheet is the lowest plate in Building view. Alt+Left/Right on a sheet tab, or its context menu, provides the same action. Sorting changes only the view order: sheet IDs, endpoint pairing, travel times, seed, recorded matrices and GA results remain unchanged. An elevator may visually skip a sheet; this does not create an intermediate stop.

Use a tab's **⋯ → Name / floor label** to name it later (for example `B1`, `2F`, or `Lab`). The stable internal ID is kept. This dialog also exposes replacement, pixel rules and removal. **Options** retains the detailed configuration behind closed groups.

## Edit a route

Use **+ Node** or right-click the map to add at the pointer. The raised blue pressed button, crosshair and placement banner remain visible while the tool is armed. Escape exits placement. Drag pins on the top-down sheet to reposition them; invalid wall/clearance drops roll back. Drag empty space to box-select, then right-click or press Delete to remove the selection. **Undo** or Ctrl/Cmd+Z restores edits.

Drag the right-hand route blocks to reorder stops. The first becomes the green start, the last the red finish, and intermediate nodes remain gray. Optional **Endpoints** selectors and Alt+Up/Down offer equivalent reordering.

A* previews the current sequence before GA. Cross-sheet legs use reachable elevator channels selected by walking plus elevator time, not screen-space proximity. Old preview replies cannot overwrite newer edits. Building view supports selecting delivery nodes and directly editing elevator handles; delivery pins are moved in the top-down view.

Zero or one node is editable; two nodes support preview. GA requires at least one intermediate delivery node. Start/finish attributes are stored but excluded from order weights and service-time sums while the nodes act as endpoints.

## Connect elevator entrances

The **+ Elevator** button sits beside **+ Node**. With one sheet it offers **Upload map** or **Blank sheet** to add the other map. With multiple sheets, click the first entrance, then an entrance on another sheet. In top-down mode the UI switches to another sheet for the second click; any other valid sheet can be selected. In Building view either plate can be clicked directly. No coordinate form or floor-label assignment is required.

Elevators are channels, not delivery stops. Creating or moving a channel never adds to the route list. Every channel keeps explicit A/B sheet IDs and coordinates. Names or overlapping artwork never imply connectivity.

Click a channel chip, square entrance marker or connection line to show its compact endpoint dock. Click an A/B sheet chip to relocate that end. In Building view, drag a square entrance or a handle near either end of the line onto a sheet. The target plate, line and coordinate readout update during dragging. On release, only that endpoint is committed; routes and preflight update immediately afterward. A wall, out-of-bounds or same-sheet drop restores the old position. A cancelled pointer gesture changes nothing. Stale routes are hidden while a channel is being dragged.

The dock's **More options** exposes sheet selection, direction-dependent waiting times, door-cycle/ride times and deletion. It is the same state as advanced **Options → Floors & elevators**, not a separate graph. Three bundled reference scans remain available there; they are not assumed to be aligned floors or to have calibrated scale.

### Incomplete links

An unset coordinate remains `null`, not `(0,0)` or a guessed free position. Drafts can be applied, exported and imported before both endpoints are placed.

Before route search or creation of a GA job, preflight checks for missing endpoints, missing floors, same-floor pairs, blocked/out-of-bounds positions, and disconnected route nodes. An enabled invalid link blocks calculation and identifies the affected endpoint. Disabled drafts are warnings and excluded from routing; the requested route must still be connected through other valid links.

The building view shows a one-ended link as a dashed half-link with a question mark and the missing endpoint label. This is a visual placeholder only: it never enters a path or fills in coordinates. When neither endpoint exists, the link remains listed as incomplete in the sidebar.

Replacing a floor map clears that floor's elevator coordinates for repositioning. Removing a floor removes its route nodes after confirmation but preserves dangling elevator references for repair. Disabled connections can remain unfinished without creating fake connectivity.

## Order priorities and optimization

Select an intermediate node to set **Importance**, **Already waited**, and **Patience**. Waiting and patience are displayed in minutes and converted to seconds. Patience is the total desired waiting window since order creation, not remaining time. Risk, local speed, service time and forbidden visit positions are under **More conditions**.

Press **Run GA scheduling** to optimize only the intermediate order. **SAW** controls Sower multi-world elite exchange. The observatory is collapsed before a run and opens automatically when GA starts. It shows actual generations, cost curves, retained elites and migration records. Ready, armed, checking, blocked, computing and done states have text/icon feedback as well as color; disabled planning has a reason in its tooltip. Replay or select a generation/world; unchecking **Show evolving routes** displays the final generation. **Use this solution** explicitly adopts the viewed permutation as the editable route.

Retained elite rows are actual sorted population members (up to five displayed per world); duplicates can occur during convergence. New/retained compares route identity with the same world's preceding generation, not ancestry. Migration records identify the exchanged permutation and its source/destination worlds.

After a completed run, expand **Weights & results** for W/D/T matrices. Click a cell to inspect the actual walking and elevator segments. **Formulas & actual values** contains feature contributions, sigmoid weights and objective components. Start/finish destination columns in W are zero. Route, geometry and scoring edits invalidate old GA results. View-only sheet reordering or renaming (and undoing those changes) preserves the recorded result.

## Language and saved scenes

The main editor defaults to **English** on first launch. Switch to **繁體中文** in the header or settings dialog; the preference is saved in browser storage when available. Application buttons, context menus, tooltips, accessibility labels, validation errors, status messages, evolution summaries and formula descriptions switch together. User-provided names and mathematical symbols are not translated. Language changes do not alter the scene, seed, matrices or recorded results.

Scene JSON preserves original imported bytes, classification options, the reviewed planning grids, physical scales, ordered nodes, portal drafts, settings and seed. Editing a Floor ID remaps its node and elevator references. Replacing geometry removes affected route nodes after confirmation and clears elevator coordinates for repositioning. Schema-2 scenes can be imported: their explicit endpoint or return location becomes the final node. Archived views at `/studio` and `/legacy` remain available for compatibility; the language switch belongs to the main editor.

## Map rules and limits

Direct planning grids remain 4–512 px per side, at most 2 MB each. The reviewed image importer accepts PNG, JPEG, PGM and BMP up to 8 MB, 8192 px per side and 16 million pixels. Larger images are classified before explicit conservative integer reduction; any wall or unknown pixel blocks its output cell. You must confirm the preview; until a real source scale is provided, metrics use the explicitly displayed assumed scale. Narrow passages can close during reduction. A scene supports four floors, 524,288 total cells, 12 elevator links, 32 route nodes (30 intermediate orders), and a 12 MB request.

Grayscale at or below the obstacle threshold is blocked. Brighter cells are traversable; gray increases cost. Transparency becomes black. A per-floor unknown grayscale value can be explicitly blocked. Obstacles and map boundaries are conservatively inflated by `ceil(radius/resolution)` cells using a square kernel. Diagonal movement cannot cut blocked corners.

The blank starter and populated demo are synthetic; bundled reference scans retain their source provenance. Use independent floor grids, not a perspective rendering of several floors. Connections are bidirectional with direction-dependent estimated waiting times. Elevator height is excluded from D; D measures walking distance on the selected minimum-time portal path. Both D and T can therefore be asymmetric.

This is a single-robot, static-order simulator, without live SLAM, elevator queue/capacity simulation or multi-robot collision avoidance. Patience is a soft objective. Risk is a consequence coefficient, not a calibrated probability. GA is heuristic; improvement is relative to the feasible input-order baseline, not a guarantee of global optimality. Sower worlds share one background thread. The candidate budget is `population × (generations + 1) × effective_worlds ≤ 300,000`.

## Development

```bash
python -m unittest discover -s tests -v
pip install playwright
python -m playwright install chromium
python tests/browser_editor.py
python tests/browser_portals.py
python tests/browser_map_import.py
python tests/browser_workbench.py
```

The browser scripts start their own local HTTP server. On environments where browser navigation is restricted, `--offline-harness --chromium /usr/bin/chromium` uses an isolated DOM/Canvas with a bridge to the real local API. That mode does not validate native browser networking or CSP and does not modify browser policy. Test artifacts are written to the ignored `test-artifacts/` directory.

After capturing the workbench and map-import screenshots, regenerate the README screenshot animation with:

```bash
python scripts/build_sheet_gif.py
```

The shared English/Traditional Chinese catalogue is `web/locales.json`. Tests check matching keys/placeholders, English defaults, localized diagnostics, and unchanged model/results across language switches. For algorithm formulas and units, see the [mathematical model](math_model.md).
