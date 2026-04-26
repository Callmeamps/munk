import pytest
from munk.hashing import hash_content, hash_file


def test_hash_content():
    content = "hello world"
    h = hash_content(content)
    assert h.startswith("sha256:")
    assert len(h) == 71  # "sha256:" + 64 hex chars


def test_hash_content_different_inputs():
    h1 = hash_content("foo")
    h2 = hash_content("bar")
    assert h1 != h2


def test_hash_content_same_input():
    h1 = hash_content("same")
    h2 = hash_content("same")
    assert h1 == h2


def test_hash_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("file content")
    h = hash_file(str(test_file))
    assert h.startswith("sha256:")


def test_hash_file_nonexistent():
    with pytest.raises(FileNotFoundError):
        hash_file("/nonexistent/file.txt")
