import io
import json

from nix_auto_follow.cli import LockFile, start, update_flake_lock


def test_simple_follow_flake() -> None:
    with open("tests/fixtures/has_follow.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        # precondition:
        assert flake_lock.nodes["nixpkgs"] != flake_lock.nodes["nixpkgs_2"]
        modified_lock = update_flake_lock(flake_lock)
        # postcondition:
        assert modified_lock.nodes["nixpkgs"] == modified_lock.nodes["nixpkgs_2"]


def test_simple_root_has_follow_flake() -> None:
    with open("tests/fixtures/root_has_follow.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        # precondition:
        assert flake_lock.nodes["nixpkgs"] != flake_lock.nodes["nixpkgs_2"]
        modified_lock = update_flake_lock(flake_lock)
        # postcondition:
        assert modified_lock.nodes["nixpkgs"] == modified_lock.nodes["nixpkgs_2"]


def test_full_start() -> None:
    with open("tests/fixtures/root_has_follow.json") as f:
        stdout = io.StringIO()
        start(stdin=f, stdout=stdout)
        flake_lock = LockFile.from_dict(json.loads(stdout.getvalue()))
        assert flake_lock.root == "root"
