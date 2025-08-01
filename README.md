# nix-auto-follow

[![built with nix](https://builtwithnix.org/badge.svg)](https://builtwithnix.org)
![github master branch workflow](https://github.com/fzakaria/nix-auto-follow/actions/workflows/main_nix.yml/badge.svg?branch=main)

```console
❯ nix run github:fzakaria/nix-auto-follow -- --help
usage: auto-follow [-h] [--in-place] [filename]

Update nix flake.lock file to autofollow.

positional arguments:
  filename        The path to the flake.lock file.

options:
  -h, --help      show this help message and exit
  --in-place, -i  Write the output back to the same file.
```

> A (python) script to achieve automatically following all flake inputs for Nix.

If you have used [Nix](https://nixos.org) flakes, you likely encountered something like this 🤢

```nix
std.url = "github:divnix/std";
std.inputs.devshell.follows = "devshell";
std.inputs.nixago.follows = "nixago";
std.inputs.nixpkgs.follows = "nixpkgs";

hive.url = "github:divnix/hive";
hive.inputs.colmena.follows = "colmena";
hive.inputs.disko.follows = "disko";
hive.inputs.nixos-generators.follows = "nixos-generators";
hive.inputs.nixpkgs.follows = "nixpkgs";
```

Why is this **follows** necessary?

It's in fact not _necessary_ but it makes the Nix evaluation simpler.

Rather than using the exact Nix flake commit your dependency desires, we are _overriding it_, with one we have likely already declared.

This has the effect of making our graph smaller, which is faster to evaluate and likely build.

> Note: Although it's _faster_ it's _less correct_ since we are deviating from what the authors of the flake desired.

Writing all those `follows` can get real teadious, and it's tough to even know you did it all... surely there has to be a better way!

There is with this script 🥳

Simply run the script which will modify your `flake.lock` file. Commit the change and voila!

```console
❯ auto-follow -i
```

## Validation

The `auto-follow` tool includes a _check mode_ ; so that you can validate you are correctly following everything.

```console
❯ auto-follow -c
All ok!
```

This will fail (exit code 1) if not everything can be deduped.

```console
❯ auto-follow -c
Node a has input nixpkgs pointing to nixpkgs_2 which is not the same as b's nixpkgs which is nixpkgs_3 in the lockfile.
Please add 'nixpkgs.url = "github:nixos/nixpkgs/nixos-23.11"' or 'nixpkgs.url = "github:nixos/nixpkgs/nixos-23.05"'
```

Note: This can still happen _even after modifying your lock file_.
The reason for this is that if the top-level Nix expression (your application _flake.nix_) does not include all possible flakes, then
there is no way for us to know which of the two choices we should consolidate to. The tool prints a friendly message showing some of the possible
options to select amongst.

## Development
Running the development shell should drop you into a shell with all the required dependencies and the editable installation already done.

```console
❯ nix develop
```
