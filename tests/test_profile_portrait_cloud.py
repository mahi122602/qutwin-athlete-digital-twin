"""Cold cloud instances provision verified weights; concurrent users share them."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import sys
import threading
import time
from types import SimpleNamespace
import urllib.error

import numpy as np
from PIL import Image, ImageDraw
import pytest
from services import profile_portrait as portrait


ASSET = b'isolated-test-model-bytes-not-a-real-onnx-file'


class Response(BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data))}


@pytest.fixture
def cold_cache(monkeypatch, tmp_path):
    path = tmp_path / 'server-cache' / 'u2net_human_seg.onnx'
    monkeypatch.setenv('QUTWIN_PORTRAIT_MODEL', str(path))
    monkeypatch.setattr(portrait, 'MODEL_SHA256', hashlib.sha256(ASSET).hexdigest())
    portrait._cached_session.cache_clear()
    portrait.prepare_portrait.cache_clear()
    yield path
    portrait._cached_session.cache_clear()
    portrait.prepare_portrait.cache_clear()


def runtime(monkeypatch, calls):
    class Session:
        def __init__(self, path, **kwargs):
            calls.append((path, kwargs))
            time.sleep(.02)  # Expose duplicate construction during a cold-start race.

        def get_inputs(self):
            return [SimpleNamespace(name='input')]

        def run(self, _, inputs):
            assert inputs['input'].shape == (1, 3, 320, 320)
            output = np.zeros((1, 1, 320, 320), dtype=np.float32)
            output[:, :, 25:300, 75:245] = 1
            return [output]
    monkeypatch.setitem(sys.modules, 'onnxruntime', SimpleNamespace(
        SessionOptions=SimpleNamespace, InferenceSession=Session))


def test_first_normal_photo_downloads_verifies_and_prepares_without_running_setup(monkeypatch, cold_cache):
    requests, sessions = [], []
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', lambda request, **kw:
                        requests.append(request.full_url) or Response(ASSET))
    runtime(monkeypatch, sessions)
    image = Image.new('RGB', (160, 200), (80, 120, 100))
    photo = BytesIO(); image.save(photo, 'JPEG')
    result = portrait.prepare_portrait(photo.getvalue())
    assert portrait.portrait_info(result)['prepared']
    assert cold_cache.read_bytes() == ASSET
    assert requests == [portrait.MODEL_URL]
    assert len(sessions) == 1
    assert sessions[0][1]['providers'] == ['CPUExecutionProvider']
    # Saved PNGs and later inference reuse the cached session and model.
    assert portrait.prepare_portrait(result) == result
    assert portrait.get_session() is portrait.get_session()
    assert len(requests) == len(sessions) == 1


def test_existing_verified_model_is_reused_without_network(monkeypatch, cold_cache):
    cold_cache.parent.mkdir(); cold_cache.write_bytes(ASSET)
    def unexpected(*a, **kw):
        raise AssertionError('A valid cache must not be downloaded again')
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', unexpected)
    assert portrait.ensure_model(download=True) == cold_cache


def test_corrupt_model_is_repaired_atomically(monkeypatch, cold_cache):
    cold_cache.parent.mkdir(); cold_cache.write_bytes(b'partial-old-model')
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', lambda *a, **kw: Response(ASSET))
    assert portrait.ensure_model(download=True) == cold_cache
    assert cold_cache.read_bytes() == ASSET
    assert not list(cold_cache.parent.glob('*.download'))


def test_wrong_checksum_never_becomes_the_installed_model(monkeypatch, cold_cache):
    cold_cache.parent.mkdir(); cold_cache.write_bytes(b'old-incomplete-model')
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', lambda *a, **kw: Response(b'not-the-model'))
    with pytest.raises(portrait.PortraitProcessingError) as caught:
        portrait.ensure_model(download=True)
    assert caught.value.code == 'MODEL_INVALID'
    assert cold_cache.read_bytes() == b'old-incomplete-model'
    assert not list(cold_cache.parent.glob('*.download'))


def test_failed_download_cleans_up_and_a_retry_can_succeed(monkeypatch, cold_cache):
    def fail(*a, **kw):
        raise urllib.error.URLError('test network interruption')
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', fail)
    with pytest.raises(portrait.PortraitProcessingError) as caught:
        portrait.ensure_model(download=True)
    assert caught.value.code == 'MODEL_DOWNLOAD'
    assert not cold_cache.exists()
    assert not list(cold_cache.parent.glob('*.download'))
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', lambda *a, **kw: Response(ASSET))
    assert portrait.ensure_model(download=True) == cold_cache


def test_simultaneous_first_uploads_share_one_download_and_one_session(monkeypatch, cold_cache):
    requests, sessions = [], []
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', lambda *a, **kw:
                        requests.append(True) or Response(ASSET))
    runtime(monkeypatch, sessions)
    barrier = threading.Barrier(4)
    def load():
        barrier.wait(timeout=5)
        return portrait.get_session()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: load(), range(4)))
    assert all(session is results[0] for session in results)
    assert len(requests) == len(sessions) == 1


def test_session_initialisation_can_retry_after_a_failed_download(monkeypatch, cold_cache):
    sessions = []
    runtime(monkeypatch, sessions)
    def fail(*a, **kw):
        raise urllib.error.URLError('test network interruption')
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', fail)
    with pytest.raises(portrait.PortraitProcessingError):
        portrait.get_session()
    monkeypatch.setattr(portrait.urllib.request, 'urlopen', lambda *a, **kw: Response(ASSET))
    assert portrait.get_session() is portrait.get_session()
    assert len(sessions) == 1


def test_transparent_cutout_does_not_require_a_model_or_a_download(monkeypatch, cold_cache):
    def unexpected(*a, **kw):
        raise AssertionError('Transparent cutouts must not need model inference')
    monkeypatch.setattr(portrait, 'get_session', unexpected)
    image = Image.new('RGBA', (80, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((20, 10, 60, 95), fill=(80, 120, 100, 255))
    photo = BytesIO(); image.save(photo, 'PNG')
    result = portrait.prepare_portrait(photo.getvalue())
    assert portrait.portrait_info(result)['prepared']
    assert not cold_cache.exists()
