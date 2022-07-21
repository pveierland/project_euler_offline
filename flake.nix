{
  description = "Project Euler Offline";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-21.11";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = (import nixpkgs { inherit system; }).pkgs;
    in
    {
      devShell.${system} = pkgs.mkShell
        {
          nativeBuildInputs = with pkgs; [
            okular
            pandoc
            python39
            python39Packages.beautifulsoup4
            texlive.combined.scheme-full
          ];
        };
    };
}
