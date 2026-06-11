from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("oh-my-field")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"
