# Usage guide

[Overview](../README.md) · [Mathematical model](math_model.md)

## Installation

The README covers Conda. Alternatively, use Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8000. Use `python app.py --port 8001` when the port is occupied. Keep the server on localhost; this local simulator does not provide authentication for public deployment.

## Edit a route

Use **Add node** or right-click the map to add at the pointer. Drag pins to reposition them; a drop on a wall or inside clearance rolls back. Drag empty space to box-select, then right-click or press Delete to remove the selection. **Undo** or Ctrl/Cmd+Z restores edits.

Drag the right-hand list to reorder stops. The first node becomes the green start, the last the red finish, and intermediate nodes remain gray. Start/finish selectors move an existing node to either end. Alt+Up/Down provides keyboard reordering.

A* previews the current sequence without running GA. Cross-floor legs use reachable elevators selected by total walking and elevator time, not screen-space proximity. Old preview replies cannot overwrite newer edits. The stacked view is for inspection; select a floor tab to edit positions.

Zero or one node is an editable map. Two nodes support route preview. GA requires at least one intermediate delivery node. Endpoint attributes are stored but excluded from order weights and service-time sums while the nodes act as endpoints.

## Upload maps and pair elevators

Open **Settings → Floors & elevators**. Upload one or several independent top-down costmaps. Review each image in the import dialog: set its Floor ID and source m/px, choose pixel rules, inspect the classification and clearance layers, and confirm. Three pinned reference rasters from `Graph_nodes_path_planning` are available from the reference picker. See [Map import](semantic_maps.md). Each floor has its own meters-per-pixel scale. This editor changes maps and their node/portal metadata; it does not paint or reconstruct walls in the raster.

Create an elevator such as `Ea`, choose its two floors, and select **Place on map** for each endpoint. Click traversable space on the corresponding floor. For floor IDs `1F` and `2F`, the labels become `Ea_1F ↔ Ea_2F`; `Eb_1F ↔ Eb_2F` is a separate elevator. Pairing comes from the explicit link record, never similar names or overlapping pixels.

Drag an existing portal to reposition it. Click or right-click its marker to edit the pair, clear an endpoint, disable the link, or remove the pair. Exact coordinates and forward/reverse waiting, door-cycle and ride times are available in expanded controls.

### Incomplete links

An unset coordinate remains `null`, not `(0,0)` or a guessed free position. Drafts can be applied, exported and imported before both endpoints are placed.

Before route search or creation of a GA job, preflight checks for missing endpoints, missing floors, same-floor pairs, blocked/out-of-bounds positions, and disconnected route nodes. An enabled invalid link blocks calculation and identifies the affected endpoint. Disabled drafts are warnings and excluded from routing; the requested route must still be connected through other valid links.

The building view shows a one-ended link as a dashed half-link with a question mark and the missing endpoint label. This is a visual placeholder only: it never enters a path or fills in coordinates. When neither endpoint exists, the link remains listed as incomplete in the sidebar.

Replacing a floor map clears that floor's elevator coordinates for repositioning. Removing a floor removes its route nodes after confirmation but preserves dangling elevator references for repair. Disabled connections can remain unfinished without creating fake connectivity.

## Order priorities and optimization

Select an intermediate node to set **Importance**, **Already waited**, and **Patience**. Waiting and patience are displayed in minutes and converted to seconds. Patience is the total desired waiting window since order creation, not remaining time. Risk, local speed, service time and forbidden visit positions are under **More conditions**.

Press **Run GA scheduling** to optimize only the intermediate order. **SAW** controls Sower multi-world elite exchange. The observatory shows actual generations, cost curves, retained elites and migration records. Replay or select a generation/world; unchecking **Show evolving routes** displays the final generation. **Use this solution** explicitly adopts the viewed permutation as the editable route.

Retained elite rows are actual sorted population members (up to five displayed per world); duplicates can occur during convergence. New/retained compares route identity with the same world's preceding generation, not ancestry. Migration records identify the exchanged permutation and its source/destination worlds.

After a completed run, expand **Weights & results** for W/D/T matrices. Click a cell to inspect the actual walking and elevator segments. **Formulas & actual values** contains feature contributions, sigmoid weights and objective components. Start/finish destination columns in W are zero. Input edits invalidate old GA results.

## Language and saved scenes

The main editor defaults to **English** on first launch. Switch to **繁體中文** in the header or settings dialog; the preference is saved in browser storage when available. Application buttons, context menus, tooltips, accessibility labels, validation errors, status messages, evolution summaries and formula descriptions switch together. User-provided names and mathematical symbols are not translated. Language changes do not alter the scene, seed, matrices or recorded results.

Scene JSON preserves original imported bytes, classification options, the reviewed planning grids, physical scales, ordered nodes, portal drafts, settings and seed. Editing a Floor ID remaps its node and elevator references. Replacing geometry removes affected route nodes after confirmation and clears elevator coordinates for repositioning. Schema-2 scenes can be imported: their explicit endpoint or return location becomes the final node. Archived views at `/studio` and `/legacy` remain available for compatibility; the language switch belongs to the main editor.

## Map rules and limits

Direct planning grids remain 4–512 px per side, at most 2 MB each. The reviewed image importer accepts PNG, JPEG, PGM and BMP up to 8 MB, 8192 px per side and 16 million pixels. Larger images are classified before explicit conservative integer reduction; any wall or unknown pixel blocks its output cell. You must confirm the preview and physical scale before using the result. Narrow passages can close during reduction. A scene supports four floors, 524,288 total cells, 12 elevator links, 32 route nodes (30 intermediate orders), and a 12 MB request.

Grayscale at or below the obstacle threshold is blocked. Brighter cells are traversable; gray increases cost. Transparency becomes black. A per-floor unknown grayscale value can be explicitly blocked. Obstacles and map boundaries are conservatively inflated by `ceil(radius/resolution)` cells using a square kernel. Diagonal movement cannot cut blocked corners.

The bundled maps are synthetic examples, not measured LiDAR. Use independent floor grids, not a perspective rendering of several floors. Connections are bidirectional with direction-dependent estimated waiting times. Elevator height is excluded from D; D measures walking distance on the selected minimum-time portal path. Both D and T can therefore be asymmetric.

This is a single-robot, static-order simulator, without live SLAM, elevator queue/capacity simulation or multi-robot collision avoidance. Patience is a soft objective. Risk is a consequence coefficient, not a calibrated probability. GA is heuristic; improvement is relative to the feasible input-order baseline, not a guarantee of global optimality. Sower worlds share one background thread. The candidate budget is `population × (generations + 1) × effective_worlds ≤ 300,000`.

## Development

```bash
python -m unittest discover -s tests -v
pip install playwright
python -m playwright install chromium
python tests/browser_editor.py
python tests/browser_portals.py
```

Both browser scripts start their own local HTTP server. On environments where browser navigation is restricted, `--offline-harness --chromium /usr/bin/chromium` uses an isolated DOM/Canvas with a bridge to the real local API. That mode does not validate native browser networking or CSP and does not modify browser policy. Test artifacts are written to the ignored `test-artifacts/` directory.

After capturing the editor and portal screenshots, regenerate the README screenshot animation with:

```bash
python scripts/build_editor_gif.py
```

The shared English/Traditional Chinese catalogue is `web/locales.json`. Tests check matching keys/placeholders, English defaults, localized diagnostics, and unchanged model/results across language switches. For algorithm formulas and units, see the [mathematical model](math_model.md).
