{
  description = "Demonstration Flake";

  inputs = {
    a.url = path:./a;
    b = {
      url = path:./b;
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
    nixpkgs-stable.follows = "nixpkgs";
  };

  outputs = {
    self,
    a,
    b,
    nixpkgs,
    nixpkgs-stable,
  }: {
    versions = {
      a.nixpkgs = a.versions.nixpkgs;
      b.nixpkgs = b.versions.nixpkgs;
      nixpkgs = nixpkgs.lib.version; 
      nixpkgs-stable = nixpkgs-stable.lib.version;
    };
  };
}
