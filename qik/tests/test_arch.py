import pytest

import qik.arch


@pytest.mark.parametrize(
    "system, arch, machine, expected",
    [
        ("Windows", "64bit", "_", "win-64"),
        ("Windows", "32bit", "_", "win-32"),
        ("Linux", "64bit", "x86_64", "linux-64"),
        ("Linux", "64bit", "aarch64", "linux-aarch64"),
        ("Linux", "64bit", "ppc64le", "linux-ppc64le"),
        ("Linux", "32bit", "_", "linux-32"),
        ("Linux", "64bit", "_", "unknown"),
        ("Darwin", "64bit", "arm64", "osx-arm64"),
        ("Darwin", "64bit", "_", "osx-64"),
        ("Darwin", "32bit", "_", "unknown"),
        ("Unknown", "32bit", "_", "unknown"),
    ],
)
def test_get(mocker, system, arch, machine, expected):
    mocker.patch("platform.system", autospec=True, return_value=system)
    mocker.patch("platform.architecture", autospec=True, return_value=(arch, "_"))
    mocker.patch("platform.machine", autospec=True, return_value=machine)
    assert qik.arch.get() == expected
