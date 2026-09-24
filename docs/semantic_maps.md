# Reviewed costmap import

Choose **Upload map** on the left or **+ Sheet** beside the tabs. Select multiple files to review one at a time. Sheet IDs and initial display names are assigned automatically; floor labeling can wait. The original and robot-clear preview appear first. **Scale & classification options** contains the editable ID, name, physical source scale and classification preset. No floor number or physical scale is inferred from a filename. The initial source scale is 0.1 m/px and is explicitly labeled assumed until edited.

## Preview first

Compare the original image with **Pixel classes**, **Planning grid** or **Robot clearance**. Click **Use this map** to confirm the review and add it to the scene. There is no separate acceptance checkbox. For physical distance/clearance calculations, supply the measured source scale rather than relying on the displayed assumption. No A* search or GA job runs during classification. The main map has matching Original / Pixel classes / Planning grid views; changing a view never changes the route grid.

- **Auto suggestion** uses the grayscale histogram to choose between occupancy-style and traversable-gray rules. It is a heuristic, not semantic recognition of a building.
- **LiDAR / occupancy** and **Graph repository scans** block dark pixels and mid-gray unknown regions. Pixels at or above the free threshold are free unless colored or transparent.
- **Gray areas are traversable** explicitly treats intermediate, achromatic gray as higher-cost floor. Do not select it for unknown scan backgrounds.
- **Custom colors only** starts with everything unknown. Add RGB color rules, optionally using the exact-source-pixel eyedropper, and choose wall, unknown, costly or free. Unmatched colors stay unknown. Color tolerance is the maximum absolute difference in any RGB channel, from 0 to 64. Overlapping rules use wall > unknown > costly > free. Fully or partly transparent pixels always remain unknown.

Thresholds, black/white inversion and color rules are under **Adjust thresholds & colors**. Auto detection never opens holes, removes furniture, erases text, or infers doors or elevators. Colored annotations are treated as unknown unless explicitly mapped. Prefer raw scan rasters over plot screenshots: white plotting margins and scan artifacts are not reliably distinguishable from white floor by color alone.

## Source size, reduction and scale

The importer accepts PNG, JPEG, PGM or BMP, up to 8 MB, 8192 px per side, and 16 million pixels. The planning grid remains at most 512 px per side; choose 384 or 256 only when suitable for the application. EXIF orientation is applied before coordinates are assigned.

For source width/height `(W,H)` and chosen grid side limit `M`, the integer reduction factor is `f = ceil(max(W,H)/M)`. Classification occurs **before** reduction. A wall or unknown source pixel blocks the entire corresponding output cell. Partial edge blocks are padded unknown. The new grid scale is `source_m_per_px × f`; there is no non-uniform stretching. Source point `(x,y)` belongs to grid cell `(floor(x/f), floor(y/f))`. Existing robot inflation is then applied at the new physical scale.

This preserves blocked source pixels but can close narrow doors. A connected-region count and the actual remaining robot-clear area are shown in the review. They describe the discretized model, not physical navigability. Use a better-scaled/cropped source map when detail is insufficient; do not reduce the real robot's radius just to force a path.

The normalized planning raster contains `0` for walls and unknown, `200` for costly cells, and `255` for free cells. The existing threshold and `gray_cost` still apply to this raster. The source/class previews are display-only; robot-clear preview and backend A* consume the same normalized raster and settings.

## Floor and elevator editing

Each imported map is an independent sheet. Add an optional display label later through its tab menu. Names such as `B1`, `1F` and `2F` do not change connectivity. A Floor ID edit updates route nodes and both sides of affected elevator pairs together. Drag sheet tab grips to set the stacked view order, bottom to top; names alone do not imply elevation or physical alignment.

Use **+ Elevator** beside **+ Node**, then click entrances on two different sheets. Select a channel to rebind its endpoints, or drag the endpoint/line handles in Building view. Elevator channels never become delivery stops. `Ea_1F ↔ Ea_2F` is one link; `Eb_1F ↔ Eb_2F` is another. Missing, blocked, out-of-bounds or disconnected endpoints are still rejected by preflight before A* or GA. A one-ended link is shown as a half-link; no missing coordinate is guessed.

Original image bytes and classification rules are retained in scene JSON. Use **Pixel rules…** to reclassify without uploading again. When geometry changes, the editor asks to remove that floor's route nodes and clears elevator positions for fresh placement. Reclassification also clears elevator positions; unchanged-coordinate route nodes are checked against the new mask. The scene still supports four floors, 524288 planning cells, 12 elevator links and a 12 MB request. Large originals count toward the scene request limit.

## Reference image provenance

The three bundled PNGs are unchanged copies of `imgs/map_1.png`, `imgs/map_2.png`, and `imgs/map_6.png` from `a0665x/Graph_nodes_path_planning` at commit `12e874932ab445f2f6ab6689757446c9247df5c7`. Their source paths and Git blob hashes are in `data/reference_maps/provenance.json`, alongside the source Apache-2.0 license. The application requires no network access to load them.

These images demonstrate scan compatibility. They are not asserted to be a single building, aligned floors, or supplied with calibrated physical scale. The user assigns floor IDs, scale and actual elevator positions. Test elevator points are artificial test placements, not extracted real elevator locations.

For an audit of all PNG/JPEG files in a checkout of the source repository:

```bash
python scripts/audit_reference_maps.py ../Graph_nodes_path_planning/imgs
```

The report records source dimensions, hashes, selected rules, reduction factor, pixel counts and connectivity. Successful decoding and classification do not certify a collision-free real robot route.
