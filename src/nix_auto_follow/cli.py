import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, TextIO


@dataclass
class ProgramArguments:
    filename: str = "flake.lock"
    in_place: bool = False


def update_flake_lock(input_data: str) -> str:
    # Load the JSON data from the input
    flake_lock: Dict[str, Any] = json.loads(input_data)

    # Start at root
    root_inputs: Dict[str, str] = flake_lock["nodes"]["root"]["inputs"]

    # Update all nodes with root inputs
    for key, ref in root_inputs.items():
        # key is the name of the input flake
        # ref is the ref in the nodes

        value = flake_lock["nodes"][ref]

        # for each key, find all other uses of it in lockfile to get
        # all the nodes to override.
        # We will set the value of it in nodes to the value stored
        # above.
        for node in flake_lock["nodes"].values():
            if "inputs" in node and key in node["inputs"]:
                duplicate_ref = node["inputs"][key]
                # if the type of the ref is a list, then it's already
                # using follows in the flake.nix so skip it.
                if duplicate_ref is list:
                    continue
                # now overwrite it!
                flake_lock["nodes"][duplicate_ref] = value

    return json.dumps(flake_lock, indent=2)


def start(args: list[str] = sys.argv[1:], stdin: TextIO = sys.stdin) -> None:
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

    program_args: ProgramArguments = parser.parse_args(
        args, namespace=ProgramArguments()
    )
    # Read the content of the file
    with open(program_args.filename, "r") as f:
        input_data = f.read()

    modified_data = update_flake_lock(input_data)
    if program_args.in_place:
        # Write the modified JSON back to the file
        with open(program_args.filename, "w") as f:
            f.write(modified_data)
    else:
        # Write the modified JSON to stdout
        print(modified_data)
