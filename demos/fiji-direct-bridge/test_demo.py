import json
import os
import subprocess
import threading
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pytest
import tifffile

from bridge_demo_server import BridgeState, create_server


@pytest.fixture
def running_server():
    state = BridgeState(
        intensity=np.arange(35, dtype=np.float32).reshape(5, 7),
        lifetime=(np.arange(35, dtype=np.float32).reshape(5, 7) / 10.0),
    )
    server = create_server('127.0.0.1', 0, 'test-token', state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f'http://{host}:{port}', state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_status_reports_protocol_without_authentication(running_server):
    base_url, _ = running_server

    with urlopen(f'{base_url}/v1/status') as response:
        payload = json.load(response)

    assert response.status == 200
    assert payload == {
        'protocol': 'flimkit-fiji',
        'protocol_version': 1,
    }


def test_image_endpoint_requires_pairing_token(running_server):
    base_url, _ = running_server

    with pytest.raises(HTTPError) as caught:
        urlopen(f'{base_url}/v1/images/intensity.tif')

    assert caught.value.code == 401


@pytest.mark.parametrize('image_id', ['intensity', 'lifetime'])
def test_authorized_image_round_trips_as_float_tiff(running_server, image_id):
    base_url, state = running_server
    request = Request(
        f'{base_url}/v1/images/{image_id}.tif',
        headers={'Authorization': 'Bearer test-token'},
    )

    with urlopen(request) as response:
        received = tifffile.imread(BytesIO(response.read()))

    assert response.status == 200
    assert response.headers['Content-Type'] == 'image/tiff'
    np.testing.assert_array_equal(received, getattr(state, image_id))
    assert received.dtype == np.float32


def test_authenticated_geojson_roi_is_received_exactly(running_server):
    base_url, state = running_server
    payload = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'properties': {'name': 'Cell 1'},
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[1.25, 2.5], [4.5, 2.5], [1.25, 2.5]]],
            },
        }],
    }
    request = Request(
        f'{base_url}/v1/rois',
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/geo+json',
        },
    )

    with urlopen(request) as response:
        reply = json.load(response)

    assert response.status == 200
    assert reply == {'received_features': 1}
    assert state.received_rois == [payload]


def test_installed_fiji_fetches_images_and_posts_roi(running_server):
    fiji_path = os.environ.get('FIJI_PATH')
    if not fiji_path:
        pytest.skip('set FIJI_PATH to run the live Fiji demo test')
    assert fiji_path is not None
    script = Path(__file__).with_name('FijiBridgeDemo.groovy')
    assert script.exists(), f'missing Fiji demo script: {script}'
    base_url, state = running_server

    completed = subprocess.run(
        [
            fiji_path,
            '--headless',
            '--run',
            str(script),
            f'baseUrl="{base_url}",token="test-token"',
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert 'FIJI_IMAGES_OK intensity=34.0 lifetime=3.4' in output, output
    assert 'FIJI_ROI_POST_OK features=1' in output, output
    assert len(state.received_rois) == 1
    feature = state.received_rois[0]['features'][0]
    assert feature['properties']['name'] == 'Fiji polygon'
    assert feature['geometry']['coordinates'] == [
        [[1.25, 2.5], [4.5, 2.5], [3.0, 4.0], [1.25, 2.5]],
    ]
