# Dispatch Lab

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
