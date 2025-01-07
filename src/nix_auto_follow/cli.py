import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, TextIO
from urllib.parse import urlencode


@dataclass
class ProgramArguments:
    filename: str = "flake.lock"
    in_place: bool = False
    check: bool = False


@dataclass
class Node:
    inputs: dict[str, str | list[str]] | None = None
    remaining: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        inputs = data.pop("inputs", None)
        remaining = data
        return cls(inputs, remaining)

    def to_dict(self) -> dict[str, Any]:
        """Convert the Node to a dictionary.

        In order to minimize diff with the original lockfile,
        we only include the `inputs` key if it is not None.
        """
        if self.inputs is None:
            return self.remaining
        else:
            return {"inputs": self.inputs, **self.remaining}

    def get_url(self) -> str:
        """
        Should reconstruct the Flake URL for the given Node.

        @see https://nix.dev/manual/nix/2.22/command-ref/new-cli/nix3-flake#types
        """
        if "original" not in self.remaining:
            raise ValueError("Node does not have a locked attribute.")
        original = self.remaining["original"]
        ref = f"/{original['ref']}" if "ref" in original else ""
        rev = f"/{original['rev']}" if "rev" in original else ""
        rev_or_ref = next((x for x in [rev, ref] if x), "")

        match original["type"]:
            case "git":
                base_url = f"git+{original['url']}"
                filtered_params = {
                    k: (1 if v is True else 0 if v is False else v)
                    for k, v in original.items()
                    if k in ["rev", "ref", "submodules", "shallow"]
                    and v not in (None, "")
                }
                query_string = urlencode(filtered_params)
                full_url = f"{base_url}?{query_string}" if query_string else base_url
                return full_url
            case "github":
                return f"github:{original['owner']}/{original['repo']}{rev_or_ref}"
            case "gitlab":
                return f"gitlab:{original['owner']}/{original['repo']}{rev_or_ref}"
            case "sourcehut":
                return f"sourcehut:{original['owner']}/{original['repo']}{rev_or_ref}"
            case "path":
                return f"file:{original['path']}"
            case "indirect":
                return f"{original['id']}{ref}{rev}"
            case _:
                raise ValueError(f"Unknown type {original['type']}")


@dataclass
class LockFile:
    root: str
    version: int
    nodes: dict[str, Node] = field(default_factory=dict)

    @property
    def root_node(self) -> Node:
        return self.nodes[self.root]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LockFile":
        root = data["root"]
        version = data["version"]
        nodes = {key: Node.from_dict(value) for key, value in data["nodes"].items()}
        return cls(root, version, nodes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {key: value.to_dict() for key, value in self.nodes.items()},
            "root": self.root,
            "version": self.version,
        }


def check_lock_file(flake_lock: LockFile) -> bool:
    success = True

    for name, node in flake_lock.nodes.items():

        if node.inputs is None:
            continue

        for key, ref in node.inputs.items():
            if isinstance(ref, list):
                continue

            for other_name, other_node in flake_lock.nodes.items():

                if other_node.inputs is None:
                    continue

                for other_key, other_ref in other_node.inputs.items():
                    if isinstance(other_ref, list):
                        continue

                    if key != other_key:
                        continue

                    if flake_lock.nodes[ref] != flake_lock.nodes[other_ref]:
                        print(
                            f"Node {name} has input {key} pointing to {ref} which is not the same as {other_name}'s {other_key} which is {other_ref} in the lockfile."  # noqa: E501
                        )
                        print(
                            f"Please add '{key}.url = \"{flake_lock.nodes[ref].get_url()}\"' or '{other_key}.url = \"{flake_lock.nodes[other_ref].get_url()}\"'"  # noqa: E501
                        )  # noqa: E501
                        success = False

    return success


def update_flake_lock(flake_lock: LockFile) -> LockFile:
    # Start at root
    root_inputs = flake_lock.root_node.inputs

    if root_inputs is None:
        return flake_lock

    # map each node's inputs to their references, e.g. for
    #
    # a.inputs = {"nixpkgs": "nixpkgs_1"}
    # b.inputs = {"nixpkgs": "nixpkgs_2"}
    # root.inputs = {"nixpkgs": "nixpkgs_3"}
    #
    # this generates {"nixpkgs": ["nixpkgs_1", "nixpkgs_2", "nixpkgs_3"]}
    input_refs: dict[str, list[str]] = {}
    for node in flake_lock.nodes.values():
        if node.inputs is None:
            continue
        for node_input_key, node_input_ref in node.inputs.items():
            if isinstance(node_input_ref, list):
                continue
            input_refs.setdefault(node_input_key, []).append(node_input_ref)

    # for each node input that matches a root node input, replace it
    # with the root node's input definition; e.g. for
    #
    # a.inputs = {"nixpkgs": "nixpkgs_1"}
    # b.inputs = {"nixpkgs": "nixpkgs_2"}
    # root.inputs = {"nixpkgs": "nixpkgs_3"}
    # input_refs = {"nixpkgs": ["nixpkgs_1", "nixpkgs_2", "nixpkgs_3"]}
    #
    # rewrite replace the definitions of "nixpkgs_1" and "nixpkg_2"
    # with "nixpkgs_3"'s definition
    for key, ref in root_inputs.items():
        if isinstance(ref, list):
            continue
        for node_ref in input_refs.get(key, ()):
            flake_lock.nodes[node_ref] = flake_lock.nodes[ref]

    return flake_lock


def start(
    args: list[str] = sys.argv[1:],
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> None:
    parser = argparse.ArgumentParser(
        description="Update nix flake.lock file to autofollow."
    )
    parser.add_argument(
        "filename",
        help="The path to the flake.lock file. '-' for stdin.",
        default="flake.lock",
        nargs="?",
    )
    parser.add_argument(
        "--in-place",
        "-i",
        action="store_true",
        help="Write the output back to the same file.",
    )
    parser.add_argument(
        "--check",
        "-c",
        action="store_true",
        help="Checks whether all entries in your lockfile are follows or equivalent.",
    )

    program_args: ProgramArguments = parser.parse_args(
        args, namespace=ProgramArguments()
    )

    if program_args.filename == "-":
        input_data = stdin.read()
    else:
        # Read the content of the file
        with open(program_args.filename, "r") as f:
            input_data = f.read()

    # Load the JSON data from the input
    flake_lock_json: dict[str, Any] = json.loads(input_data)

    if program_args.check:
        if not check_lock_file(LockFile.from_dict(flake_lock_json)):
            exit(1)
        else:
            print("All ok!")
            return

    modified_data = json.dumps(
        update_flake_lock(LockFile.from_dict(flake_lock_json)).to_dict(), indent=2
    )

    if program_args.in_place:
        if program_args.filename == "-":
            raise ValueError("Cannot use --in-place with stdin.")
        # Write the modified JSON back to the file
        with open(program_args.filename, "w") as f:
            f.write(modified_data + "\n")
    else:
        # Write the modified JSON to stdout
        print(modified_data, file=stdout)
