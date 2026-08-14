# Demo 001: direct Fiji bridge

## Question

**Given** a small HTTP server running inside a future FLIMKit add-on,
**when** an installed Fiji process connects over localhost,
**then** can Fiji receive intensity and lifetime images as TIFF and send an
ROI back as GeoJSON without a manual file exchange?

## Approach

This demo contains:

- `bridge_demo_server.py`: a minimal authenticated localhost server;
- `FijiBridgeDemo.groovy`: a Fiji/SciJava demo client;
- `test_demo.py`: Python protocol tests and a live Fiji integration test.

The fixture serves asymmetric 5×7 `float32` arrays. The last pixel is `34.0`
in the intensity image and `3.4` in the lifetime image. The asymmetry catches
shape and coordinate-order mistakes.

The Fiji client:

1. fetches both TIFF images with a bearer token;
2. decodes them in memory with ImageJ `Opener.openTiff`;
3. checks the shape and known pixel values;
4. posts one named polygon ROI with fractional `[x, y]` coordinates;
5. exits with observable success markers.

## Run

Python-only protocol checks:

```bash
cd demos/fiji-direct-bridge
PYTHONPATH=. python -m pytest test_demo.py -q
```

Live Fiji check on this machine:

```bash
cd /home/zhenyuan/Documents/FLIMKit-fiji-bridge-demo/demos/fiji-direct-bridge
FIJI_PATH=/home/zhenyuan/Applications/Fiji.app/fiji \
PYTHONPATH=. \
/tmp/flimkit-issue22-venv/bin/python -m pytest test_demo.py -q
```

Verified result on 2026-08-14:

```text
6 passed in 10.44s
```

## Evidence

The live Fiji process returned:

```text
FIJI_IMAGES_OK intensity=34.0 lifetime=3.4
FIJI_ROI_POST_OK features=1
```

The Python side then verified the exact ROI payload:

```json
{
  "properties": {"name": "Fiji polygon"},
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[1.25, 2.5], [4.5, 2.5], [3.0, 4.0], [1.25, 2.5]]]
  }
}
```

## What worked

- Fiji connected directly to a Python localhost server.
- Bearer-token authentication worked.
- Fiji decoded TIFF bytes without writing a user-facing temporary file.
- Both image shapes and `float32` values survived exactly.
- Fiji posted GeoJSON directly back to Python.
- ROI names and fractional coordinates survived exactly.
- The headless run completed deterministically.

## What this does not prove

- It does not use FLIMKit GUI state or its plugin bindings.
- It does not use Fiji's ROI Manager yet.
- It does not open display windows because the test is headless.
- It does not test GeoJSON import into FLIMKit's current ROI manager.
- It does not test BigWarp or registered ROI transfer.
- It does not define the production protocol, lifecycle, or error UI.

## Surprise

Groovy property syntax `image.processor` selected ImageJ's boolean
`isProcessor()` method instead of `getProcessor()`. The demo client therefore
uses the explicit Java call:

```groovy
image.getProcessor().getf(x, y)
```

The production Fiji plugin should prefer explicit Java method calls where
ImageJ exposes both `isX()` and `getX()` forms.

## Verdict: VALIDATED

Direct local communication is feasible with the proposed transport:

```text
FLIMKit Python add-on ← authenticated localhost HTTP → Fiji plugin
```

TIFF is suitable for the two image planes, and GeoJSON is suitable for ROI
messages. No PyImageJ/JVM embedding is needed.

## Recommendation for the real build

Before turning this demo into production code:

1. fix and test FLIMKit's real GeoJSON round trip;
2. add stable public plugin bindings for current images and ROIs;
3. replace the Groovy demo script with a small SciJava command;
4. add Fiji ROI Manager conversion and GUI-mode tests;
5. keep registration in Fiji and reject mismatched image dimensions.
