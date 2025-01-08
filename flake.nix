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
        nixpkgsSystem = import nixpkgs { inherit system; };

        nixpkgsSystemUnstable = (import nixpkgs-unstable {
          inherit system;
        });

        lib = nixpkgsSystem.lib;
        pkgs = nixpkgsSystem.pkgs;
        pkgs-unstable = nixpkgsSystemUnstable.pkgs;

        pythonEnvironment = pkgs.python312.withPackages (p: (
          lib.unique (lib.flatten (map (source: import source { pythonPackages = p; }) pythonEnvironmentSources))
        ));

        pythonEnvironmentSources = [
          ./python-requirements.nix
        ];
      in
      {
        devShell = (
          pkgs.mkShell
            {
              nativeBuildInputs = (
                with pkgs; [
                  okular
                  pandoc
                  pkgs-unstable.ruff
                  pkgs-unstable.uv
                  pythonEnvironment
                  texlive.combined.scheme-full
                ]
              );
              shellHook = ''
                UV_PYTHON_ENV_SITE_PACKAGES="${pythonEnvironment}/${pythonEnvironment.sitePackages}"
              '';
            }
        );
      }
    );
}
