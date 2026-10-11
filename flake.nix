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
            pkgs.just
          ];
          shellHook = ''
            export UV_PYTHON="${python}/bin/python"

            if [ ! -x .venv/bin/python ]; then
              uv venv --python "$UV_PYTHON" .venv
            fi

            # Keep the venv aligned with the committed uv.lock.
            stamp=.venv/.uv-sync-stamp
            need_sync=0
            if [ ! -f "$stamp" ]; then
              need_sync=1
            elif [ pyproject.toml -nt "$stamp" ] || [ uv.lock -nt "$stamp" ]; then
              need_sync=1
            fi

            if [ "$need_sync" = 1 ]; then
              uv sync --extra web --extra host --group dev
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
