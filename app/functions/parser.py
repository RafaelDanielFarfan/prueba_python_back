import ast
import math
from collections.abc import Callable
from types import CodeType

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
ImplicitCallable = Callable[[FloatArray, FloatArray, FloatArray], FloatArray]

VARIABLES = frozenset("xyz")

CONSTANTS: dict[str, float] = {"pi": np.pi, "e": np.e}

FUNCTIONS: dict[str, Callable[[FloatArray], FloatArray]] = {
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "sqrt": np.sqrt,
    "exp": np.exp,
    "log": np.log,
    "abs": np.abs,
}

ALLOWED_NAMES: dict[str, object] = {**FUNCTIONS, **CONSTANTS}

BINARY_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
UNARY_OPERATORS = (ast.UAdd, ast.USub)

# Defensa adicional: la gramática ya se valida sobre el AST antes de compilar.
SAFE_GLOBALS: dict[str, object] = {"__builtins__": {}}

_PROBE = np.linspace(0.25, 0.75, 3)


class ExpressionError(ValueError):
    pass


class _Whitelist(ast.NodeTransformer):
    """Acepta solo la gramática del enunciado y rechaza cualquier otro nodo del AST.

    Las constantes enteras se convierten a ``float``: así ``9**9**9**9`` desborda en
    lugar de calcular un entero gigantesco.
    """

    def generic_visit(self, node: ast.AST) -> ast.AST:
        raise ExpressionError(f"Construcción no permitida: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression) -> ast.AST:
        node.body = self.visit(node.body)
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if not isinstance(node.op, BINARY_OPERATORS):
            raise ExpressionError(f"Operador no permitido: {type(node.op).__name__}")
        node.left, node.right = self.visit(node.left), self.visit(node.right)
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        if not isinstance(node.op, UNARY_OPERATORS):
            raise ExpressionError(f"Operador no permitido: {type(node.op).__name__}")
        node.operand = self.visit(node.operand)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ExpressionError("Solo se permiten constantes numéricas reales")
        try:
            number = float(value)
        except OverflowError as error:
            raise ExpressionError("Constante numérica fuera de rango") from error
        if not math.isfinite(number):
            raise ExpressionError("Constante numérica fuera de rango")
        return ast.copy_location(ast.Constant(number), node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id not in VARIABLES and node.id not in CONSTANTS:
            raise ExpressionError(f"Nombre no permitido: {node.id}")
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        function = node.func
        if not isinstance(function, ast.Name) or function.id not in FUNCTIONS:
            raise ExpressionError("Función no permitida")
        if node.keywords or len(node.args) != 1 or isinstance(node.args[0], ast.Starred):
            raise ExpressionError(f"{function.id} recibe exactamente un argumento")
        node.args = [self.visit(node.args[0])]
        return node


def _compile(expression: str) -> CodeType:
    try:
        tree = ast.parse(expression, mode="eval")
        tree = ast.fix_missing_locations(_Whitelist().visit(tree))
        return compile(tree, "<expression>", "eval")
    except ExpressionError:
        raise
    except SyntaxError as error:
        raise ExpressionError(f"Sintaxis inválida: {error.msg}") from error
    except (ValueError, RecursionError, MemoryError) as error:
        raise ExpressionError("Expresión inválida o demasiado compleja") from error


def compile_expression(expression: str) -> ImplicitCallable:
    code = _compile(expression)

    def evaluate(x: FloatArray, y: FloatArray, z: FloatArray) -> FloatArray:
        namespace = {**ALLOWED_NAMES, "x": x, "y": y, "z": z}
        result = eval(code, SAFE_GLOBALS, namespace)  # noqa: S307
        return np.broadcast_to(np.asarray(result, dtype=np.float64), np.broadcast(x, y, z).shape)

    return evaluate


def check_expression(expression: str) -> None:
    """Valida la expresión compilándola y evaluándola sobre unos puntos de prueba."""
    evaluate = compile_expression(expression)
    try:
        evaluate(_PROBE, _PROBE, _PROBE)
    except Exception as error:
        raise ExpressionError(f"No se pudo evaluar la expresión: {error}") from error


def evaluate_point(expression: str, x: float, y: float, z: float) -> float:
    evaluate = compile_expression(expression)
    return float(evaluate(x, y, z))
