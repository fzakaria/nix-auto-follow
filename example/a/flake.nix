{
  description = "A dependency Flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-23.11";
    c = {
      url = path:./c;
    };
  };

  outputs = {
    self,
    nixpkgs,
    c,
  }: {
    versions = {
      nixpkgs = nixpkgs.lib.version;
      c.nixpkgs = c.nixpkgs.lib.version;
    };
  };
}
