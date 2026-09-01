# Carriage

A typewriter drawing studio. Drop a photograph; it is typed in ink on cream paper. Join, post a page to the family wall, and open a drawing to see the original photo beside it.

## Demo

**Live app:** [https://carriage-typewriter.fly.dev](https://carriage-typewriter.fly.dev)

1. Open the wall.
2. **Join** (or **Sign in**).
3. **Studio** — drop a photo. It types as you move the sliders.
4. **Post** when the page looks right.
5. Click a drawing to compare it with the photograph.

The first load after the machine has been idle can take a few seconds.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open [http://127.0.0.1:5001](http://127.0.0.1:5001).
