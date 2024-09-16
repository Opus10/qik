import pathlib

import qik.errors
import qik.hash
import qik.shell
import qik.venv


def test_globs(tmpdir, mocker):
    tmpdir = pathlib.Path(tmpdir)
    mocker.patch("qik.conf.root", autospec=True, return_value=str(tmpdir))
    qik.shell.exec("git init")

    assert qik.hash.globs() == ""
    assert qik.hash.globs("my_file") == "99aa06d3014798d86001c324468d497f"

    (tmpdir / "my_file").write_text("hello!")
    assert qik.hash.globs("my_file") == "99aa06d3014798d86001c324468d497f"

    # Adding to git should affect the hash
    qik.shell.exec("git add my_file")
    assert qik.hash.globs("my_file") == "132383b5d4ac79bf3afd3d2b5e5411a2"

    # Modifying file should affect hash
    (tmpdir / "my_file").write_text("hello there!")
    assert qik.hash.globs("my_file") == "9d82a0ed5bf63cc6faf372a8d18d98ae"

    # Committing shouldn't affect hash, but a different code path will
    # be used
    qik.shell.exec("git add my_file && git commit -m 'commit'")
    assert qik.hash.globs("my_file") == "9d82a0ed5bf63cc6faf372a8d18d98ae"

    # Add another path for globbing, which doesn't affect the hash since it's
    # not in git
    (tmpdir / "another_file").write_text("hello!")
    assert qik.hash.globs("my_file", "another_file") == "9d82a0ed5bf63cc6faf372a8d18d98ae"

    qik.shell.exec("git add another_file && git commit -m 'another file'")
    assert qik.hash.globs("my_file", "another_file") == "9faff63beca6b3a9fc15692c1bcf8c38"

    # Removing the files without changing the git index hits another edge case
    (tmpdir / "my_file").unlink()
    (tmpdir / "another_file").unlink()
    assert qik.hash.globs("my_file", "another_file") == "0f25ee40196b9e61afe8675a7a441be3"

    # Removing the files from the git index will return the hash back to the original value
    qik.shell.exec("git add -u && git commit -m 'commit'")
    assert qik.hash.globs("my_file", "another_file") == "99aa06d3014798d86001c324468d497f"


def test_pydists():
    venv = qik.venv.active()
    assert qik.hash.pydists("pytest", venv=venv) == "b57d851a0617e17d0a9cb1d93fe9099a"
    assert (
        qik.hash.pydists("pytest", "pytest-cov", venv=venv) == "705e4096c5edbeda860aa1745170bff1"
    )


def test_strs():
    assert qik.hash.strs("str1") == "b1c699cb2c59f52c4cb89ca551547bb4"
    assert qik.hash.strs("str1", "str2") == "244ffb46948d48baf3c76226c4344018"


def test_val():
    assert qik.hash.val("str1") == "b1c699cb2c59f52c4cb89ca551547bb4"
    assert qik.hash.val(b"str1") == "b1c699cb2c59f52c4cb89ca551547bb4"
