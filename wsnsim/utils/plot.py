"""Plot helpers (optional)."""

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def simple_line(x, y, title=None):
    if plt is None:
        raise RuntimeError("matplotlib not available")
    plt.figure()
    plt.plot(x, y)
    if title:
        plt.title(title)
    return plt
