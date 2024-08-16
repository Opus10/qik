from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Iterator

import boto3
import moto.server
import pytest


@pytest.fixture(scope="module", autouse=True)
def mock_s3():
    server = moto.server.ThreadedMotoServer(ip_address="127.0.0.1", port=5000)
    server.start()
    conn = boto3.resource(
        "s3",
        aws_access_key_id="fake",
        aws_secret_access_key="fake",
        region_name="us-west-2",
        endpoint_url="http://127.0.0.1:5000",
    )
    conn.create_bucket(
        Bucket="qik-cache-test", CreateBucketConfiguration={"LocationConstraint": "us-west-2"}
    )
    yield
    server.stop()


@pytest.fixture(autouse=True)
def patch_aws_creds(mocker):
    mocker.patch.dict(
        os.environ,
        {
            "PROJECT__AWS_ACCESS_KEY_ID": "fake",
            "PROJECT__AWS_SECRET_ACCESS_KEY": "fake",
            "PROJECT__AWS_ENDPOINT_URL": "http://127.0.0.1:5000",
        },
    )
    yield


def shell(
    cli_invocation, cwd: str | None = "test_project", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cli_invocation, shell=True, text=True, capture_output=True, cwd=cwd, env=env
    )


@contextlib.contextmanager
def _edit_hello_py() -> Iterator[None]:
    """Edit a/hello.py to break cache."""
    hello_path = pathlib.Path("test_project/a/hello.py")
    orig_hello = hello_path.read_bytes()
    shell(f'echo "\n" >> {hello_path}', cwd=None)

    yield

    hello_path.write_bytes(orig_hello)


def test_full_run():
    """Test a full run of invoking `qik`.

    Note - a command explicitly fails, causing the whole run to fail.
    """

    # Uncached full run
    shutil.rmtree("test_project/._qik", ignore_errors=True)
    shutil.rmtree("test_project/.qik")
    result = shell("qik")
    assert "An unexpected error happened" not in result.stdout
    assert result.returncode == 1

    # Remote-only cached run
    shutil.rmtree("test_project/._qik", ignore_errors=True)
    assert "An unexpected error happened" not in result.stdout
    assert shell("qik").returncode == 1

    # Fully cached run
    assert "An unexpected error happened" not in result.stdout
    assert shell("qik").returncode == 1


def test_individual_commands():
    """Test running individual selected commands."""

    # Uncached full run
    shutil.rmtree("test_project/._qik", ignore_errors=True)
    shutil.rmtree("test_project/.qik")
    assert shell("qik modular_format modular_lint").returncode == 0

    # Fully cached run
    assert shell("qik modular_format modular_lint").returncode == 0


def test_serial_logging_output():
    """Use -n 1 to invoke a different logger"""
    assert shell("qik -n 1").returncode == 1


def test_ls():
    """Verify --ls returns commands"""
    assert len(shell("qik --ls").stdout.split("\n")) > 15


def test_selectors():
    """Test various cache / git selectors."""
    # Ensure repo cache is warm
    assert shell("qik --cache-status cold --cache-type repo --ls --fail").returncode == 0

    # Editing a project file should result in --since returning results
    with _edit_hello_py():
        assert len(shell("qik --since HEAD").stdout.split("\n")) > 5
        assert shell("qik --cache-status cold --cache-type repo --ls --fail").returncode == 1

    # Return the cache back to normal
    assert shell("qik").returncode == 1


def test_env_ctx():
    """Override qik ctx with env vars."""
    env = os.environ | {
        "QIK__LS": "True",
        "QIK__CACHE_STATUS": "cold",
        "QIK__CACHE_TYPES": "repo",
        "QIK__FAIL": "True",
    }
    assert shell("qik", env=env).returncode == 0


@contextlib.contextmanager
def daemon(cmd: str, wait_for_output: str) -> Iterator[None]:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        bufsize=1,
        universal_newlines=True,
        cwd="test_project",
    )

    start_time = time.time()
    while time.time() - start_time < 5:
        output = process.stdout.readline().strip()
        if wait_for_output in output:
            break
    else:
        raise Exception("Could not start daemon")

    try:
        yield
    finally:
        process.terminate()


@pytest.mark.skipif(sys.platform.startswith("linux"), reason="Test does not run on Linux")
def test_watch():
    """Test watching commands."""
    with daemon("qik --watch", wait_for_output="Watching for changes..."):
        hello_path = pathlib.Path("test_project/a/hello.py")
        orig_hello = hello_path.read_bytes()
        shell(f'echo "\n" >> {hello_path}', cwd=None)
        time.sleep(2)
        assert hello_path.read_bytes() == orig_hello
