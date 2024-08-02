import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, TextIO


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
        return {"inputs": self.inputs, **self.remaining}

    def get_url(self) -> str:
        if "original" not in self.remaining:
            raise ValueError("Node does not have a locked attribute.")
        locked = self.remaining["original"]
        match locked["type"]:
            case "github":
                return f"github:{locked['owner']}/{locked['repo']}/{locked['ref']}"
            case "gitlab":
                return f"gitlab:{locked['owner']}/{locked['repo']}/{locked['ref']}"
            case "bitbucket":
                return f"bitbucket:{locked['owner']}/{locked['repo']}/{locked['ref']}"
            case "path":
                return f"file:{locked['path']}"
            case _:
                raise ValueError(f"Unknown type {locked['type']}")


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
            "root": self.root,
            "version": self.version,
            "nodes": {key: value.to_dict() for key, value in self.nodes.items()},
        }


def check_lock_file(flake_lock: LockFile) -> bool:

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
                            f"Please add '{key}.url = \"{flake_lock.nodes[ref].get_url()}\"' or '{other_key}.url = \"{flake_lock.nodes[other_ref].get_url()}'"  # noqa: E501
                        )  # noqa: E501
                        return False

    return True


def update_flake_lock(flake_lock: LockFile) -> LockFile:
    # Start at root
    root_inputs = flake_lock.root_node.inputs

    if root_inputs is None:
        return flake_lock

    # Update all nodes with root inputs
    for key, ref in root_inputs.items():
        # key is the name of the input flake
        # ref is the ref in the nodes

        # if the type of the ref is a list, then it's already
        # using follows in the flake.nix so skip it.
        if isinstance(ref, list):
            continue

        value = flake_lock.nodes[ref]

        # for each key, find all other uses of it in lockfile to get
        # all the nodes to override.
        # We will set the value of it in nodes to the value stored
        # above.
        for node in flake_lock.nodes.values():
            if node.inputs is None:
                continue

            if key in node.inputs:
                duplicate_ref = node.inputs[key]
                # if the type of the ref is a list, then it's already
                # using follows in the flake.nix so skip it.
                if isinstance(duplicate_ref, list):
                    continue
                # now overwrite it!
                flake_lock.nodes[duplicate_ref] = value

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
        help="The path to the flake.lock file.",
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

    if not stdin.isatty():
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
        # Write the modified JSON back to the file
        with open(program_args.filename, "w") as f:
            f.write(modified_data)
    else:
        # Write the modified JSON to stdout
        print(modified_data, file=stdout)
