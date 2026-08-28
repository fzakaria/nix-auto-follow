"""
End-to-end tests that run the real `nix` against real flakes.

The unit tests can only assert what we *believe* Nix considers a stable
lockfile. These assert it: they lock a flake, run auto-follow over the result,
and lock it again. If Nix rewrites anything on that second pass, our output
was not stable and the user gets the entry back on their next `nix build`.

Everything here uses `path:` flakes with absolute paths, so no network is
needed and no `parent` field (which relative path flakes carry) muddies the
comparison.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from nix_auto_follow.cli import start

NIX_FLAGS = ["--extra-experimental-features", "nix-command flakes"]


def nix_available() -> bool:
    if shutil.which("nix") is None:
        return False
    try:
        return (
            subprocess.run(
                ["nix", *NIX_FLAGS, "flake", "--help"],
                capture_output=True,
                timeout=60,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


requires_nix = pytest.mark.skipif(
    not nix_available(), reason="needs a nix with flakes enabled"
)


def write_flake(directory: Path, inputs: str, version: str = "none") -> None:
    flake_nix = "\n".join(
        [
            "{",
            f"  inputs = {{{inputs}}};",
            f'  outputs = _: {{ ok = true; version = "{version}"; }};',
            "}",
            "",
        ]
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "flake.nix").write_text(flake_nix)


def nix_flake_lock(directory: Path) -> dict[str, Any]:
    subprocess.run(
        ["nix", *NIX_FLAGS, "flake", "lock"],
        cwd=directory,
        capture_output=True,
        check=True,
        timeout=300,
    )
    return read_lock(directory)


def read_lock(directory: Path) -> dict[str, Any]:
    with open(directory / "flake.lock") as f:
        return json.load(f)  # type: ignore[no-any-return]


@pytest.fixture
def follows_flake(tmp_path: Path) -> Path:
    """
    A flake tree that reproduces the follows-clobbering case.

    Two versions of the same dependency, `new` and `old`. The root takes
    `new`; `leaf` and `mid` take `old`, so there is real unification work to
    do. `leaf` is reached twice -- directly from the root, and through `mid`,
    which declares `leaf.inputs.p.follows = "p"`. That second edge is the one
    that produces a `leaf` node whose input is a follows path, which is the
    shape that made nix-auto-follow's output unstable.
    """
    write_flake(tmp_path / "new", "", version="new")
    write_flake(tmp_path / "old", "", version="old")
    write_flake(tmp_path / "leaf", f' p.url = "path:{tmp_path}/old"; ')
    write_flake(
        tmp_path / "mid",
        f"""
    p.url = "path:{tmp_path}/old";
    leaf = {{ url = "path:{tmp_path}/leaf"; inputs.p.follows = "p"; }};
  """,
    )
    write_flake(
        tmp_path,
        f"""
    p.url = "path:{tmp_path}/new";
    leaf.url = "path:{tmp_path}/leaf";
    mid.url = "path:{tmp_path}/mid";
  """,
    )
    return tmp_path


@requires_nix
def test_follows_flake_reproduces_the_duplicate(follows_flake: Path) -> None:
    """Guard the fixture: without the duplicate there is nothing to test."""
    nodes = nix_flake_lock(follows_flake)["nodes"]

    # the root reaches `leaf` directly, and `mid` reaches its own copy ...
    assert nodes["root"]["inputs"]["leaf"] == "leaf"
    assert nodes["mid"]["inputs"]["leaf"] == "leaf_2"
    # ... whose only difference is the follows declaration.
    assert nodes["leaf"]["inputs"] == {"p": "p"}
    assert nodes["leaf_2"]["inputs"] == {"p": ["mid", "p"]}

    # and there really are two versions to unify.
    versions = {
        node["original"]["path"].rsplit("/", 1)[-1]
        for name, node in nodes.items()
        if name.startswith("p")
    }
    assert versions == {"new", "old"}


@requires_nix
def test_lockfile_is_stable_after_auto_follow(follows_flake: Path) -> None:
    """
    nix flake lock -> auto-follow -> nix flake lock must be a fixed point.

    This is the regression test for follows references being flattened into
    direct ones: Nix notices the lockfile no longer matches mid's
    `leaf.inputs.p.follows = "p"` declaration and locks the entry again,
    so the tool's output ping-pongs on every rebuild.
    """
    nix_flake_lock(follows_flake)

    start(args=["--in-place", str(follows_flake / "flake.lock")])
    after_auto_follow = read_lock(follows_flake)

    assert nix_flake_lock(follows_flake) == after_auto_follow


@requires_nix
def test_auto_follow_unifies_and_still_evaluates(follows_flake: Path) -> None:
    """The point of the tool: one version of `p`, and the flake still works."""
    nix_flake_lock(follows_flake)

    start(args=["--in-place", str(follows_flake / "flake.lock")])
    nodes = read_lock(follows_flake)["nodes"]

    every_p = [node for name, node in nodes.items() if name.startswith("p")]
    assert len(every_p) > 1
    assert {node["original"]["path"].rsplit("/", 1)[-1] for node in every_p} == {"new"}
    # the follows survived the unification
    assert nodes["leaf_2"]["inputs"] == {"p": ["mid", "p"]}

    subprocess.run(
        ["nix", *NIX_FLAGS, "eval", ".#ok"],
        cwd=follows_flake,
        capture_output=True,
        check=True,
        timeout=300,
    )


@pytest.fixture
def relative_path_flake(tmp_path: Path) -> Path:
    """The same tree as `follows_flake`, wired up with relative paths."""
    write_flake(tmp_path / "new", "", version="new")
    write_flake(tmp_path / "old", "", version="old")
    write_flake(tmp_path / "leaf", ' p.url = "path:../old"; ')
    write_flake(
        tmp_path / "mid",
        """
    p.url = "path:../old";
    leaf = { url = "path:../leaf"; inputs.p.follows = "p"; };
  """,
    )
    write_flake(
        tmp_path,
        """
    p.url = "path:./new";
    leaf.url = "path:./leaf";
    mid.url = "path:./mid";
  """,
    )
    return tmp_path


@requires_nix
@pytest.mark.xfail(
    strict=False,
    reason=(
        "known limitation, not a regression: relative `path:` inputs carry a "
        "`parent` field and their locked path is resolved relative to it, so "
        "a node cannot be unified by copying content alone -- the path would "
        "have to be rewritten for the target's position in the tree. Older "
        "Nix releases do not emit `parent`, hence strict=False."
    ),
)
def test_lockfile_is_stable_for_relative_path_flakes(relative_path_flake: Path) -> None:
    nix_flake_lock(relative_path_flake)

    start(args=["--in-place", str(relative_path_flake / "flake.lock")])
    after_auto_follow = read_lock(relative_path_flake)

    assert nix_flake_lock(relative_path_flake) == after_auto_follow


@requires_nix
def test_check_agrees_with_the_stable_lockfile(follows_flake: Path) -> None:
    """`--check` must pass on exactly the output the tool produces."""
    nix_flake_lock(follows_flake)
    lock = str(follows_flake / "flake.lock")

    with pytest.raises(SystemExit):
        start(args=["--check", lock])

    start(args=["--in-place", lock])
    start(args=["--check", lock])
