"""Bounded decimal arithmetic; no eval, names, calls or filesystem operations."""

import ast
from decimal import Context, Decimal, DecimalException, localcontext
import re

from genesis_fintech.domain.models import DataError


def calculate(expression: str) -> str:
    if type(expression) is not str or not 1 <= len(expression) <= 256:
        raise DataError("invalid_expression")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        if len(list(ast.walk(tree))) > 64:
            raise DataError("expression_too_complex")

        def evaluate(node, depth=0):
            if depth > 12:
                raise DataError("expression_too_deep")
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                literal = ast.get_source_segment(expression.strip(), node)
                if literal is None or not re.fullmatch(r"\d+(?:\.\d+)?", literal):
                    raise DataError("invalid_decimal_literal")
                result = Decimal(literal)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = evaluate(node.operand, depth + 1)
                result = value if isinstance(node.op, ast.UAdd) else -value
            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                left, right = evaluate(node.left, depth + 1), evaluate(node.right, depth + 1)
                if isinstance(node.op, ast.Add):
                    result = left + right
                elif isinstance(node.op, ast.Sub):
                    result = left - right
                elif isinstance(node.op, ast.Mult):
                    result = left * right
                else:
                    result = left / right
            else:
                raise DataError("unsupported_expression")
            if not result.is_finite() or abs(result) > Decimal('1e30') or (result and result.adjusted() < -30):
                raise DataError("numeric_bound_exceeded")
            return result

        with localcontext(Context(prec=80)):
            result = evaluate(tree.body)
            output = format(result, "f").rstrip('0').rstrip('.') if '.' in format(result, 'f') else format(result, 'f')
            return "0" if result == 0 else output
    except (SyntaxError, DecimalException, RecursionError, ValueError) as exc:
        if isinstance(exc, DataError):
            raise
        raise DataError("invalid_arithmetic") from exc
