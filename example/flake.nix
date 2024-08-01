{
  description = "Demonstration Flake";

  inputs = {
    a.url = path:./a;
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
  };

  outputs = { self, a, nixpkgs }: 
  {
    versions = {
        a.nixpkgs = a.versions.nixpkgs;
        nixpkgs = nixpkgs.lib.version;
    };
    
  };
}
