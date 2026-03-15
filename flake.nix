{
  description = "Project Euler Offline";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = inputs@{ self, flake-utils, nixpkgs, nixpkgs-unstable, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pkgs-unstable = import nixpkgs-unstable { inherit system; };

        pandoc-python = pkgs.python312Packages.buildPythonPackage rec {
          pname = "pandoc";
          version = "2.4";
          src = pkgs.python312Packages.fetchPypi {
            inherit pname version;
            hash = "sha256-7NH4y7f0GAxrXbShenwadN9RmZX18Ybvgc5yqcvQ3Zo=";
          };
          propagatedBuildInputs = with pkgs.python312Packages; [
            plumbum
            ply
          ];
          doCheck = false;
        };

        pythonEnvironment = pkgs.python312.withPackages (p: [
          p.aiohttp
          p.beautifulsoup4
          p.pydash
          p.tqdm
          pandoc-python
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [
            pandoc
            pkgs-unstable.ruff
            pkgs-unstable.uv
            pythonEnvironment
            texlive.combined.scheme-full
          ];
        };
      }
    );
}
