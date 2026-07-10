"""Public-safe Nkama Fact Benchmark package."""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("nkama-fact-benchmark")
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0.1.28"

__all__ = ["__version__"]
