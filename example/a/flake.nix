{
  description = "A dependency Flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-23.11";
  };

  outputs = {
    self,
    nixpkgs,
  }: {
    versions = {
      nixpkgs = nixpkgs.lib.version;
    };
  };
}
