{
  description = "Demonstration Flake";

  inputs = {
    a.url = path:./a;
    b = {
      url = path:./b;
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
  };

  outputs = {
    self,
    a,
    b,
    nixpkgs,
  }: {
    versions = {
      a.nixpkgs = a.versions.nixpkgs;
      b.nixpkgs = b.versions.nixpkgs;
      nixpkgs = nixpkgs.lib.version;
    };
  };
}
