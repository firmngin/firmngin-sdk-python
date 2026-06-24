# Firmngin Flask Device Example

Minimal Flask project showing how to use the Firmngin Python SDK from HTTP endpoints.

## Setup

```bash
cd examples/flask_device_dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../keys.json.example keys.json
```

Replace `keys.json` with real device credentials.

## Run

```bash
flask --app app run
```

Health check:

```bash
curl http://127.0.0.1:5000/
```

Send relay state:

```bash
curl -X POST http://127.0.0.1:5000/relay \
  -H 'Content-Type: application/json' \
  -d '{"value":"on"}'
```

Upload image:

```bash
curl -X POST http://127.0.0.1:5000/image \
  -F image=@snapshot.jpg
```

Device events and endpoint actions are printed to the Flask process output.

## What It Demonstrates

- Starts `AsyncClient` in a background thread.
- Prints payment and relay command events.
- Publishes relay state with `client.push_entity(relay, value)`.
- Uploads an image with `client.upload_image(camera, file_path)`.

Flask's development server is for local development only.
Avoid the debug reloader for this example because it can start the background device worker twice.
