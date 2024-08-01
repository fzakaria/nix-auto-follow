from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nix_auto_follow")
except PackageNotFoundError:
    # If the package is not installed, don't add __version__
    pass
