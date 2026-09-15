"""Shared test helpers."""
import os
import time

import pytest


@pytest.fixture(autouse=True, scope="session")
def _web_test_mode():
    """Skip network lookups in the web app during tests (deterministic + fast).

    The web job runner calls the real pipeline (network metadata lookups) during
    preview; without this the preview-completion tests flake on lookup latency.
    """
    os.environ.setdefault("EBOOK_SORTER_WEB_TEST", "1")
    yield


@pytest.fixture
def tmp_ebook_dir(tmp_path: Path) -> Path:
    return tmp_path / "ebooks"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return out


def wait_for_status(client, job_id: str, target_status: str,
                    timeout: float = 5.0, poll: float = 0.1) -> dict:
    """Poll GET /api/jobs/{id} until status matches or timeout."""
    deadline = time.time() + timeout
    last_data = None
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        if resp.status_code != 200:
            pytest.fail(f"GET /jobs/{job_id} returned {resp.status_code}")
        last_data = resp.json()
        if last_data.get("status") == target_status:
            return last_data
        time.sleep(poll)
    pytest.fail(
        f"Job {job_id} did not reach '{target_status}' within {timeout}s. "
        f"Last status: {last_data.get('status') if last_data else 'unknown'}"
    )


@pytest.fixture
def wait_for():
    return wait_for_status
