{
  description = "Project Euler Offline";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = inputs@{ self, flake-utils, nixpkgs, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        pandoc-python = pkgs.python312Packages.buildPythonPackage rec {
          pname = "pandoc";
          version = "2.4";
          pyproject = true;
          src = pkgs.python312Packages.fetchPypi {
            inherit pname version;
            hash = "sha256-7NH4y7f0GAxrXbShenwadN9RmZX18Ybvgc5yqcvQ3Zo=";
          };
          build-system = with pkgs.python312Packages; [
            setuptools
          ];
          dependencies = with pkgs.python312Packages; [
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
            ghostscript
            imagemagick
            pandoc
            pythonEnvironment
            ruff
            (texlive.combine {
              inherit (texlive)
                scheme-small
                adjustbox
                animate
                attachfile2
                collectbox
                fancyhdr
                lastpage
                latexmk
                media9
                ragged2e
                soul
                titlesec
                ocgx2
                unicode-math
                zref
                ;
            })
            uv
          ];
        };
      }
    );
}
