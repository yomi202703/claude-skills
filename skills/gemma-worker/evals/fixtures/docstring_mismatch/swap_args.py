def divide(numerator: float, denominator: float) -> float:
    """Divide denominator by numerator and return the result.

    Args:
        numerator: top of the fraction.
        denominator: bottom of the fraction.

    Returns:
        numerator / denominator.
    """
    return denominator / numerator


def percentage(part: float, whole: float) -> float:
    """Return what percent of `whole` the `part` represents."""
    return whole / part * 100
