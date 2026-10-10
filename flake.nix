{
  description = "ai-quiz development shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
      in
      {
        devShells.default = pkgs.mkShell {
          name = "ai-quiz";
          packages = [
            python
            pkgs.uv
          ];
          shellHook = ''
            export UV_PYTHON="${python}/bin/python"

            if [ ! -x .venv/bin/python ]; then
              uv venv --python "$UV_PYTHON" .venv
            fi

            stamp=.venv/.quiz-data-installed
            need_install=0
            if [ ! -f "$stamp" ]; then
              need_install=1
            elif [ pyproject.toml -nt "$stamp" ]; then
              need_install=1
            elif find src/quiz_data src/quiz_web -type f -newer "$stamp" 2>/dev/null | grep -q .; then
              need_install=1
            fi

            if [ "$need_install" = 1 ]; then
              uv pip install --python .venv/bin/python -e ".[web,dev]"
              touch "$stamp"
            fi

            export VIRTUAL_ENV="$PWD/.venv"
            export PATH="$VIRTUAL_ENV/bin:$PATH"
            # Prefer the venv interpreter over nixpkgs python on PATH.
            unset PYTHONHOME
          '';
        };
      }
    );
}
