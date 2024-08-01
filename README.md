# nix-auto-follow

[![built with nix](https://builtwithnix.org/badge.svg)](https://builtwithnix.org)

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
> auto-follow -i
```

## Development
Running the development shell should drop you into a shell with all the required dependencies and the editable installation already done.

```console
> nix develop
```