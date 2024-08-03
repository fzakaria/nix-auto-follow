{
  lib,
  python3Packages,
  pyright,
}: let
  fs = lib.fileset;
in
  python3Packages.buildPythonApplication rec {
    name = "nix-auto-follow";
    pyproject = true;
    SETUPTOOLS_SCM_PRETEND_VERSION = "0.0.0";

    src = fs.toSource {
      root = ./.;
      fileset = fs.unions [
        ./pyproject.toml
        ./tests
        ./src
        ./setup.cfg
        ./mypy.ini
        ./Makefile
        ./.coveragerc
      ];
    };

    build-system = with python3Packages; [
      setuptools
      setuptools-scm
    ];

    dependencies = with python3Packages; [
    ];

    nativeCheckInputs = with python3Packages;
      [pytestCheckHook flake8 mypy isort black pytest-cov]
      ++ [
        # FIXME: we are still types-pygments
        types-colorama
        types-setuptools
      ]
      ++ [pyright];

    postCheck = ''
      make lint
      mkdir $htmlcov
      mv htmlcov/* $htmlcov
    '';

    outputs = [ "out" "htmlcov" ];

    meta = {
      homepage = "https://github.com/fzakaria/nix-auto-follow";
      description = "Achieve nirvana through automatically following all flake inputs.";
      license = lib.licenses.mit;
      mainProgram = "auto-follow";
    };
  }
