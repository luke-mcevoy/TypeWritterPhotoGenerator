# Carriage

Photographs, redrawn in type. A vintage machine chooses the keys for tone and line. From across the room it is a drawing. Up close it is letters.

Join, type a photograph in the studio, and post it to a shared wall. Open any page to see the original beside the drawing.

## Demos

Live app: **[https://carriage-typewriter.fly.dev](https://carriage-typewriter.fly.dev)**

| Try this | Link |
| --- | --- |
| Shared wall | [carriage-typewriter.fly.dev](https://carriage-typewriter.fly.dev) |
| Studio | [Open the studio](https://carriage-typewriter.fly.dev/studio) |
| Fish | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/7) |
| Turkey | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/6) |
| Desert | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/8) |
| Stevens | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/9) |
| Car | [Photo / Drawing / Both](https://carriage-typewriter.fly.dev/p/10) |

On a drawing page, use **Drawing**, **Photo**, and **Both** to compare the typed page with the original.

To make your own: **Join** → **Studio** → drop a photo → **Post**.

Fly’s free trial stops the machine every five minutes until a payment method is on the account. After that, the first visit following a quiet stretch may take a few seconds to wake.

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
