# Carriage

Photographs, redrawn in type. A vintage machine chooses the keys for tone and line. From across the room it is a drawing. Up close it is letters.

Join, type a photograph in the studio, and post it to a shared wall. Open any page to see the original beside the drawing.

## Demo

**Hosted app:** [https://carriage-typewriter.fly.dev](https://carriage-typewriter.fly.dev)

Fly’s free trial stops the machine every five minutes until a payment method is on the account. After that, the first visit following a quiet stretch may take a few seconds to wake.

1. Open the wall.
2. **Join** (or **Sign in**).
3. **Studio** — drop a photo. It types as you adjust.
4. **Post** when the page looks right.
5. Click a drawing for **Photo / Drawing / Both**.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001). Drawings and accounts live in `data/` (gitignored).

## Share from this Mac

Quick Cloudflare tunnels only work while this process is running. Plug the laptop in, leave the lid open, and in Terminal:

```bash
./serve-public.sh
```

Copy the `https://….trycloudflare.com` URL it prints. Closing the window, sleeping the Mac, or Ctrl+C kills that link. Posts made through the tunnel are stored in this machine’s `data/` folder, not on Fly.

## Deploy

```bash
fly deploy --app carriage-typewriter
```

SQLite and uploaded pages sit on the Fly volume mounted at `/app/data`.
