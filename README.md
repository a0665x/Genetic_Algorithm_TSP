# Dispatch Lab

Plan robot deliveries across multiple floors. Set order priorities, connect elevators, and explore obstacle-aware routes in one interactive workspace.

![Dispatch Lab walkthrough: order priorities, planned routes, floor connections, and travel-time details](docs/assets/dispatch-demo.gif)

*Screenshot walkthrough: set priorities → review routes → explore floors → inspect travel times.*

## Features

- **Multi-floor routing** with editable maps and elevator connections.
- **Simple order controls** for importance, waiting time, and patience.
- **A* + genetic optimization** for routes and delivery sequences.
- **Replay and inspection** with W/D/T matrices and scene import/export.

## Quick start

```bash
git clone https://github.com/a0665x/Genetic_Algorithm_TSP.git
cd Genetic_Algorithm_TSP
conda env create -f environment.yml
conda activate dispatch-lab
python app.py
```

Open **http://127.0.0.1:8000**. No GPU or frontend build is required.

Using an existing checkout? Run `git pull origin main` before starting the app. For a pip-based installation, see the [setup guide](docs/guide.md#installation).

## Try it

1. Start with the included two-floor example, or upload your own floor maps.
2. Select an order and adjust its importance, waiting time, and patience.
3. Run the planner, explore the route, and open calculation details when needed.

Advanced controls and formulas stay collapsed until you need them.

## Documentation

[Usage and configuration](docs/guide.md) · [Mathematical model](docs/math_model.md) · [Developer checks](docs/guide.md#development)

Local, single-robot simulation with synthetic example maps—not a hardware controller. Keep the server on localhost; do not expose it directly to the public internet.

[Apache 2.0 license](LICENSE)
