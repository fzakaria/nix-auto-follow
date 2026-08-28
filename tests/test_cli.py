import io
import json

import pytest

from nix_auto_follow.cli import (
    LockFile,
    Node,
    check_lock_file,
    collect_ignored_nodes,
    is_unified,
    start,
    update_flake_lock,
)


@pytest.mark.parametrize(
    "node, expected_url",
    [
        (
            Node.from_dict(
                {
                    "original": {
                        "owner": "nixos",
                        "ref": "nixos-24.05",
                        "repo": "nixpkgs",
                        "type": "github",
                    }
                }
            ),
            "github:nixos/nixpkgs/nixos-24.05",
        ),
        (
            Node.from_dict(
                {"original": {"owner": "nixos", "repo": "nixpkgs", "type": "github"}}
            ),
            "github:nixos/nixpkgs",
        ),
        (
            Node.from_dict({"original": {"id": "nixpkgs", "type": "indirect"}}),
            "nixpkgs",
        ),
        (
            Node.from_dict({"original": {"id": "nixpkgs", "type": "indirect"}}),
            "nixpkgs",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "id": "nixpkgs",
                        "ref": "nixos-unstable",
                        "type": "indirect",
                    }
                }
            ),
            "nixpkgs/nixos-unstable",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "id": "nixpkgs",
                        "ref": "nixos-unstable",
                        "rev": "23.11",
                        "type": "indirect",
                    }
                }
            ),
            "nixpkgs/nixos-unstable/23.11",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "type": "git",
                        "url": "https://github.com/kaeeraa/ayugram-desktop",
                    }
                }
            ),
            "git+https://github.com/kaeeraa/ayugram-desktop",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "type": "git",
                        "submodules": True,
                        "url": "https://github.com/kaeeraa/ayugram-desktop",
                    }
                }
            ),
            "git+https://github.com/kaeeraa/ayugram-desktop?submodules=1",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "type": "git",
                        "shallow": True,
                        "url": "ssh://git@github.com/mslxl/scripts.git",
                    }
                }
            ),
            "git+ssh://git@github.com/mslxl/scripts.git?shallow=1",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "type": "git",
                        "ref": "main",
                        "shallow": True,
                        "url": "ssh://git@gitlab.com/akibahmed/sops-secrects.git",
                    }
                }
            ),
            "git+ssh://git@gitlab.com/akibahmed/sops-secrects.git?ref=main&shallow=1",
        ),
        (
            Node.from_dict(
                {
                    "original": {
                        "type": "sourcehut",
                        "owner": "~rycee",
                        "repo": "nmd",
                    }
                }
            ),
            "sourcehut:~rycee/nmd",
        ),
    ],
)
def test_get_url_for_node(node: Node, expected_url: str) -> None:
    assert node.get_url() == expected_url


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
        start(args=["-"], stdin=f, stdout=stdout)
        flake_lock = LockFile.from_dict(json.loads(stdout.getvalue()))
        assert flake_lock.root == "root"


@pytest.mark.parametrize(
    "filename",
    [
        "tests/fixtures/has_follow.json",
        "tests/fixtures/root_has_follow.json",
    ],
)
def test_check_lock_file_success(filename: str) -> None:
    with open(filename) as f:
        flake_lock = LockFile.from_dict(json.load(f))
        assert not check_lock_file(flake_lock)
        # fix it
        modified_lock = update_flake_lock(flake_lock)
        assert check_lock_file(modified_lock)


def resolve(flake_lock: LockFile, ref: str | list[str]) -> str:
    """
    Resolve an input reference to a node name.

    A string is already a node name; a list is a `follows` path walked from
    the root. Raises KeyError if the reference dangles, which is what makes
    this useful as a lockfile validity check.
    """
    if isinstance(ref, str):
        if ref not in flake_lock.nodes:
            raise KeyError(f"dangling reference {ref}")
        return ref

    current = flake_lock.root
    for segment in ref:
        inputs = flake_lock.nodes[current].inputs or {}
        if segment not in inputs:
            raise KeyError(f"follows path {ref} has no '{segment}' on node {current}")
        current = resolve(flake_lock, inputs[segment])
    return current


def reachable_nodes(flake_lock: LockFile) -> set[str]:
    """Every node reachable from the root, following both kinds of reference."""
    seen: set[str] = set()
    pending = [flake_lock.root]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for ref in (flake_lock.nodes[name].inputs or {}).values():
            pending.append(resolve(flake_lock, ref))
    return seen


def assert_valid_lock_file(flake_lock: LockFile) -> None:
    """Assert every reference in the lockfile resolves to a node."""
    for name, node in flake_lock.nodes.items():
        for key, ref in (node.inputs or {}).items():
            try:
                resolve(flake_lock, ref)
            except KeyError as e:
                raise AssertionError(f"node {name} input {key}: {e}") from e


def test_follows_references_fixture_is_valid() -> None:
    """The fixture has to be a lockfile Nix would accept, or it proves nothing."""
    with open("tests/fixtures/follows_references.json") as f:
        assert_valid_lock_file(LockFile.from_dict(json.load(f)))


def test_follows_reference_is_preserved() -> None:
    """
    A `follows` declaration must survive unification.

    nixvim's flake.nix says `nuschtosSearch.inputs.nixpkgs.follows = "nixpkgs"`,
    which the lockfile stores as the path ["nixvim", "nixpkgs"]. Replacing it
    with a direct reference makes Nix consider the entry stale and re-lock it,
    so the tool's own output would be undone on the next evaluation.
    """
    with open("tests/fixtures/follows_references.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        # precondition: the two copies of nuschtosSearch are at different revs,
        # and only nixvim's copy carries the follows.
        assert flake_lock.nodes["nuschtosSearch"].remaining["locked"]["rev"] == "NS-NEW"
        assert (
            flake_lock.nodes["nuschtosSearch_2"].remaining["locked"]["rev"] == "NS-OLD"
        )
        assert flake_lock.nodes["nuschtosSearch_2"].inputs == {
            "flake-utils": "flake-utils",
            "nixpkgs": ["nixvim", "nixpkgs"],
        }

        modified_lock = update_flake_lock(flake_lock)

        # the follows survives ...
        assert modified_lock.nodes["nuschtosSearch_2"].inputs == {
            "nixpkgs": ["nixvim", "nixpkgs"]
        }
        # ... and the node still took on the canonical revision.
        assert (
            modified_lock.nodes["nuschtosSearch_2"].remaining
            == modified_lock.nodes["nuschtosSearch"].remaining
        )
        assert_valid_lock_file(modified_lock)


def test_unified_node_declares_the_canonical_revisions_inputs() -> None:
    """
    The input *keys* come from the canonical node, never from the target.

    A node has to declare the input set of the revision it claims to be.
    NS-OLD had a `flake-utils` input and NS-NEW does not, so carrying the
    target's own key over would leave the node advertising an input its own
    flake.nix no longer declares -- which Nix re-locks.
    """
    with open("tests/fixtures/follows_references.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        assert "flake-utils" in (flake_lock.nodes["nuschtosSearch_2"].inputs or {})

        modified_lock = update_flake_lock(flake_lock)

        assert "flake-utils" not in (
            modified_lock.nodes["nuschtosSearch_2"].inputs or {}
        )


def test_unification_collapses_the_duplicate_subtree() -> None:
    """
    Unifying a duplicate must also drop whatever only the duplicate pulled in.

    Preserving the target's direct references would leave flake-utils live in
    the closure, which defeats the point of the tool.
    """
    with open("tests/fixtures/follows_references.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        assert "flake-utils" in reachable_nodes(flake_lock)

        modified_lock = update_flake_lock(flake_lock)

        assert "flake-utils" not in reachable_nodes(modified_lock)
        # the duplicate nixpkgs nodes stay reachable -- unification equalises
        # their content rather than rewriting references -- but they now all
        # carry the root's revision.
        assert reachable_nodes(modified_lock) == {
            "root",
            "nixpkgs",
            "nixpkgs_2",
            "nixpkgs_3",
            "nixvim",
            "nuschtosSearch",
            "nuschtosSearch_2",
        }
        for name in ("nixpkgs_2", "nixpkgs_3"):
            assert (
                modified_lock.nodes[name].remaining
                == modified_lock.nodes["nixpkgs"].remaining
            )


def test_check_accepts_nodes_differing_only_in_follows() -> None:
    """`--check` has to accept exactly what update_flake_lock produces."""
    with open("tests/fixtures/follows_references.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        assert not check_lock_file(flake_lock)

        modified_lock = update_flake_lock(flake_lock)

        # nuschtosSearch and nuschtosSearch_2 are not equal as Nodes -- one has
        # a follows -- but they are unified, so the check must pass.
        assert (
            modified_lock.nodes["nuschtosSearch"]
            != modified_lock.nodes["nuschtosSearch_2"]
        )
        assert is_unified(
            modified_lock.nodes["nuschtosSearch"],
            modified_lock.nodes["nuschtosSearch_2"],
        )
        assert check_lock_file(modified_lock)


@pytest.mark.parametrize(
    "attribute, value",
    [
        # same rev, but pinned differently -- update_flake_lock still rewrites
        # `original`, so `--check` must not call this clean.
        ("original", {"owner": "NixOS", "repo": "nixpkgs", "type": "github"}),
        # a non-flake source unified with a flake one fails to evaluate.
        ("flake", False),
    ],
)
def test_check_catches_divergence_outside_locked(attribute: str, value: object) -> None:
    """
    Comparing only `locked` is too weak: it lets `--check` report a lockfile
    as clean that update_flake_lock would still rewrite.
    """
    with open("tests/fixtures/follows_references.json") as f:
        flake_lock = update_flake_lock(LockFile.from_dict(json.load(f)))
        assert check_lock_file(flake_lock)

        flake_lock.nodes["nixpkgs_3"].remaining[attribute] = value

        assert not check_lock_file(flake_lock)


def test_check_lock_file_fail() -> None:
    """
    This lockfile fails because there are follows beyond the root.
    We cann't figure out which follow to use so the user needs to elevate
    one to the root.
    """
    with open("tests/fixtures/non_root_follow.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        assert not check_lock_file(flake_lock)
        # try to fix it
        modified_lock = update_flake_lock(flake_lock)
        # still fails
        assert not check_lock_file(modified_lock)


def test_do_not_include_empty_inputs() -> None:
    with open("tests/fixtures/simple.json") as f:
        flake_json = json.load(f)
        flake_lock = LockFile.from_dict(flake_json)
        # precondition: inputs does not exist in original lock file
        assert "inputs" not in flake_json["nodes"]["nixpkgs"]
        assert flake_lock.nodes["nixpkgs"].inputs is None

        modified_lock = update_flake_lock(flake_lock)
        modified_lock_json = modified_lock.to_dict()
        # postcondition: inputs does not exist in modified lock file
        assert "inputs" not in modified_lock_json["nodes"]["nixpkgs"]
        assert modified_lock.nodes["nixpkgs"].inputs is None


def test_top_level_keys_sorted() -> None:
    with open("tests/fixtures/simple.json") as f:
        flake_json = json.load(f)
        # precondition: keys are sorted in original file
        assert list(flake_json.keys()) == sorted(flake_json.keys())

        flake_lock = LockFile.from_dict(flake_json)
        modified_lock = update_flake_lock(flake_lock)
        modified_lock_json = modified_lock.to_dict()

        # postcondition: keys are sorted in modified file
        assert list(modified_lock_json.keys()) == sorted(modified_lock_json.keys())


def test_collect_ignored_nodes_transitive_closure() -> None:
    with open("tests/fixtures/ignore_subtree.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        ignored = collect_ignored_nodes(flake_lock, ["pinned"])
        # the whole subtree reachable from the "pinned" root input, including
        # the nested (depth-2) nixpkgs:
        assert ignored == {"pinned", "dep", "nixpkgs_pinned"}


def test_collect_ignored_nodes_unknown_input_warns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with open("tests/fixtures/ignore_subtree.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        assert collect_ignored_nodes(flake_lock, ["nonexistent"]) == set()
        assert "does not match any root input" in capsys.readouterr().err


def test_ignore_protects_subtree_but_collapses_siblings() -> None:
    with open("tests/fixtures/ignore_subtree.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        # precondition: every nixpkgs differs.
        assert flake_lock.nodes["nixpkgs_pinned"] != flake_lock.nodes["nixpkgs_root"]
        assert flake_lock.nodes["nixpkgs_other"] != flake_lock.nodes["nixpkgs_root"]

        ignored = collect_ignored_nodes(flake_lock, ["pinned"])
        modified_lock = update_flake_lock(flake_lock, ignored)

        # the protected subtree keeps its own pin ...
        assert (
            modified_lock.nodes["nixpkgs_pinned"] != modified_lock.nodes["nixpkgs_root"]
        )
        # ... while the non-ignored sibling still collapses onto root.
        assert (
            modified_lock.nodes["nixpkgs_other"] == modified_lock.nodes["nixpkgs_root"]
        )


def test_ignore_default_collapses_everything() -> None:
    with open("tests/fixtures/ignore_subtree.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        # without an ignore list, both subtrees collapse onto root.
        modified_lock = update_flake_lock(flake_lock)
        assert (
            modified_lock.nodes["nixpkgs_pinned"] == modified_lock.nodes["nixpkgs_root"]
        )
        assert (
            modified_lock.nodes["nixpkgs_other"] == modified_lock.nodes["nixpkgs_root"]
        )


def test_check_lock_file_respects_ignore() -> None:
    with open("tests/fixtures/ignore_subtree.json") as f:
        flake_lock = LockFile.from_dict(json.load(f))
        ignored = collect_ignored_nodes(flake_lock, ["pinned"])
        modified_lock = update_flake_lock(flake_lock, ignored)
        # with the subtree ignored the remaining inputs are consistent ...
        assert check_lock_file(modified_lock, ignored)
        # ... but a plain check still flags the intentionally-kept pin.
        assert not check_lock_file(modified_lock)


def test_start_with_ignore() -> None:
    with open("tests/fixtures/ignore_subtree.json") as f:
        stdout = io.StringIO()
        start(args=["--ignore", "pinned", "-"], stdin=f, stdout=stdout)
        flake_lock = LockFile.from_dict(json.loads(stdout.getvalue()))
        assert flake_lock.nodes["nixpkgs_pinned"] != flake_lock.nodes["nixpkgs_root"]
        assert flake_lock.nodes["nixpkgs_other"] == flake_lock.nodes["nixpkgs_root"]


def test_node_keys_sorted() -> None:
    with open("tests/fixtures/root_has_follow.json") as f:
        flake_json = json.load(f)
        # precondition: keys are sorted in original file
        assert list(flake_json["nodes"].keys()) == sorted(flake_json["nodes"].keys())

        flake_lock = LockFile.from_dict(flake_json)
        modified_lock = update_flake_lock(flake_lock)
        modified_lock_json = modified_lock.to_dict()

        # postcondition: keys are sorted in modified file
        assert list(modified_lock_json["nodes"].keys()) == sorted(
            modified_lock_json["nodes"].keys()
        )
