"""Plot helpers (optional)."""

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def simple_line(x: list, y: list, title: str | None = None) -> Any:
    """Create a simple line plot.

    Args:
        x: List of x-coordinates.
        y: List of y-coordinates.
        title: Optional title for the plot.

    Returns:
        The matplotlib plot object.

    Raises:
        RuntimeError: If matplotlib is not available.
    """
    if plt is None:
        raise RuntimeError("matplotlib not available")
    plt.figure()
    plt.plot(x, y)
    if title:
        plt.title(title)
    return plt
