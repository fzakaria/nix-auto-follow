{
  description = "Achieve nirvana through automatically following all flake inputs.";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = {
    self,
    nixpkgs,
  }: let
    supportedSystems = ["x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin"];
    forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    nixpkgsFor = forAllSystems (system:
      import nixpkgs {
        inherit system;
        overlays = [
          self.overlays.default
        ];
      });
  in {
    overlays.default = final: prev: {
      all-follow = prev.callPackage ./derivation.nix {};
    };

    formatter = forAllSystems (system: (nixpkgsFor.${system}).alejandra);

    packages = forAllSystems (system: {
      default = (nixpkgsFor.${system}).all-follow;
    });

    devShells = forAllSystems (system:
      with nixpkgsFor.${system}; {
        default = mkShellNoCC {
          venvDir = "./.venv";
          packages = [
            python3Packages.pip
            # This execute some shell code to initialize a venv in $venvDir before
            # dropping into the shell
            python3Packages.venvShellHook
          ];
          # bring all the dependencies needed to build sqlelf
          inputsFrom = [all-follow];
          postVenvCreation = ''
            pip install --editable ".[dev]"
          '';
        };
      });
  };
}
