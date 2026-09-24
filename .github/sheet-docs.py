from pathlib import Path
r=Path(__file__).resolve().parents[1]
(r/'README.md').write_text('''# Dispatch Lab

Drop in a map, drag your stops, and plan a delivery route. Add more sheets and connect elevator entrances when you need them.

![Dispatch Lab: map sheets, draggable elevator channels and GA evolution](docs/assets/dispatch-demo.gif)

*Actual UI walkthrough: one sheet → connect maps → rearrange layers → explore evolution.*

## Features

- **Sheet-first editing** — upload maps, drag tabs to stack them, name floors later.
- **Direct interaction** — draggable pins, route blocks, right-click actions and undo.
- **Elevator channels** — connect two entrances; drag endpoints or line handles in the building view.
- **A* + GA scheduling** — instant ordered-route preview, SAW worlds, elite replay and optional calculation details.
- **English / 繁體中文** — switch without changing your scene or results.

## Quick start

```bash
git clone https://github.com/a0665x/Genetic_Algorithm_TSP.git
cd Genetic_Algorithm_TSP
conda env create -f environment.yml
conda activate dispatch-lab
python app.py
```

Open **http://127.0.0.1:8000**. No GPU or frontend build is required.

Existing checkout: `git pull --ff-only origin main`. For pip installation, see the [setup guide](docs/guide.md#installation).

## Try it

1. Choose **Upload map**, check the preview, and press **Use this map**. Add stops directly on the sheet.
2. Add another **Sheet** when needed. **+ Elevator** connects two map positions without adding delivery stops.
3. Drag stops or sheet tabs, then run **GA scheduling** and explore the evolution observatory.

Floor labels, image adjustments and algorithm settings remain optional. An assumed map scale is shown until you supply a real one. Incomplete channels remain visible and block planning.

## Documentation

[Maps](docs/semantic_maps.md) · [Usage](docs/guide.md) · [Mathematics](docs/math_model.md) · [Developer checks](docs/guide.md#development)

Local, single-robot simulation—not a hardware controller. Keep the server on localhost.

[Apache 2.0 license](LICENSE)
''')
p=r/'docs/guide.md';s=p.read_text()
start=s.index('## Edit a route')
end=s.index('### Incomplete links')
s=s[:start]+'''## Start with one sheet

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

''' +s[end:]
s=s.replace('The observatory shows actual generations, cost curves, retained elites and migration records.', 'The observatory is collapsed before a run and opens automatically when GA starts. It shows actual generations, cost curves, retained elites and migration records. Ready, armed, checking, blocked, computing and done states have text/icon feedback as well as color; disabled planning has a reason in its tooltip.')
s=s.replace('Input edits invalidate old GA results.', 'Route, geometry and scoring edits invalidate old GA results. View-only sheet reordering or renaming (and undoing those changes) preserves the recorded result.')
s=s.replace('The bundled maps are synthetic examples, not measured LiDAR.', 'The blank starter and populated demo are synthetic; bundled reference scans retain their source provenance.')
s=s.replace('You must confirm the preview and physical scale before using the result.', 'You must confirm the preview; until a real source scale is provided, metrics use the explicitly displayed assumed scale.')
s=s.replace('python tests/browser_portals.py\n', 'python tests/browser_portals.py\npython tests/browser_map_import.py\npython tests/browser_workbench.py\n')
s=s.replace('Both browser scripts', 'The browser scripts')
s=s.replace('After capturing the editor and portal screenshots', 'After capturing the workbench and map-import screenshots')
s=s.replace('python scripts/build_editor_gif.py','python scripts/build_sheet_gif.py')
p.write_text(s)
p=r/'docs/semantic_maps.md';s=p.read_text()
s=s.replace('Open **Settings → Floors & elevators → Upload floor**, or **Import costmap** on the left. Select multiple files to review one at a time. For each image, enter a unique **Floor ID**, a display name and the **source-image scale in meters per pixel**. No floor number or physical scale is inferred from a filename.', 'Choose **Upload map** on the left or **+ Sheet** beside the tabs. Select multiple files to review one at a time. Sheet IDs and initial display names are assigned automatically; floor labeling can wait. The original and robot-clear preview appear first. **Scale & classification options** contains the editable ID, name, physical source scale and classification preset. No floor number or physical scale is inferred from a filename. The initial source scale is 0.1 m/px and is explicitly labeled assumed until edited.')
s=s.replace('Confirm the classes and scale to add the map to your scene.', 'Click **Use this map** to confirm the review and add it to the scene. There is no separate acceptance checkbox. For physical distance/clearance calculations, supply the measured source scale rather than relying on the displayed assumption.')
s=s.replace('Each imported map is independent. Label them `B1`, `1F`, `2F` or your own IDs.', 'Each imported map is an independent sheet. Add an optional display label later through its tab menu. Names such as `B1`, `1F` and `2F` do not change connectivity.')
s=s.replace('The stacked view uses floor-list order, bottom to top;', 'Drag sheet tab grips to set the stacked view order, bottom to top;')
s=s.replace('Create an elevator such as `Ea`, choose its two floor IDs, and place its endpoints explicitly.', 'Use **+ Elevator** beside **+ Node**, then click entrances on two different sheets. Select a channel to rebind its endpoints, or drag the endpoint/line handles in Building view. Elevator channels never become delivery stops.')
p.write_text(s)
