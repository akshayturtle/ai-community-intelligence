"""Safe math evaluation tool for Agno agents."""

import math

from agno.tools import Toolkit


class CalculateTool(Toolkit):
    """Safe math evaluation tool."""

    def __init__(self):
        super().__init__(name="calculate_tool")
        self.register(self.calculate)
        self.register(self.normalize)

    def calculate(self, expression: str) -> str:
        """Evaluate a mathematical expression safely.

        Available functions: abs, max, min, round, sum, len, sqrt, log, pow
        Available constants: pi, e

        Examples:
        - calculate('(47 / 500) * 100') -> '9.4'
        - calculate('round(0.7234, 2)') -> '0.72'
        - calculate('abs(0.41 - 0.72)') -> '0.31'
        - calculate('max(85, 72, 41, 78)') -> '85'
        """
        safe_globals = {"__builtins__": {}}
        safe_locals = {
            "abs": abs, "max": max, "min": min, "round": round,
            "sum": sum, "len": len, "sqrt": math.sqrt, "log": math.log,
            "pow": pow, "pi": math.pi, "e": math.e,
        }
        try:
            result = eval(expression, safe_globals, safe_locals)
            if isinstance(result, float):
                result = round(result, 4)
            return str(result)
        except Exception as e:
            return f"CALC ERROR: {str(e)}"

    def normalize(self, value: float, min_val: float, max_val: float) -> str:
        """Normalize a value to 0-1 range.
        normalize(500, 0, 1000) -> 0.5
        Values below min -> 0, above max -> 1."""
        if max_val == min_val:
            return "0.5"
        normalized = max(0, min(1, (value - min_val) / (max_val - min_val)))
        return str(round(normalized, 4))
