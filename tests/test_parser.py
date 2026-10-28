import numpy as np
import pytest

from app.functions.parser import ExpressionError, check_expression, compile_expression


def test_compiled_expression_evaluates_arrays():
    evaluate = compile_expression("x**2 + y**2 + z**2 - 1")
    values = evaluate(np.array([0.0, 1.0]), np.array([0.0, 0.0]), np.array([0.0, 0.0]))

    np.testing.assert_allclose(values, [-1.0, 0.0])


def test_constant_expression_is_broadcast():
    evaluate = compile_expression("pi")
    values = evaluate(np.zeros(4), np.zeros(4), np.zeros(4))

    assert values.shape == (4,)


@pytest.mark.parametrize("expression", ["sin(x) * cos(y) + z", "sqrt(x**2 + y**2) - 0.5", "exp(-x) - e"])
def test_check_accepts_allowed_functions(expression):
    check_expression(expression)


@pytest.mark.parametrize("expression", ["x +* y", "open('/etc/passwd')", "__import__('os')", "foo(x)"])
def test_check_rejects_invalid_expressions(expression):
    with pytest.raises(ExpressionError):
        check_expression(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "-x + 2*y/3 - z**2",
        "+x",
        "abs(x) + log(y + 2)",
        "tan(x) - z",
        "1/x - y",
        "2*pi*e",
        "1e-3*x",
        "sin(cos(tan(x)))",
    ],
)
def test_check_accepts_documented_grammar(expression):
    check_expression(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "().__class__.__base__.__subclasses__().__len__() * 0 + x",
        "x.real",
        "[x][0]",
        "{'a': x}",
        "x if y else z",
        "(lambda: x)()",
        "[i for i in x]",
        "x < y",
        "x and y",
        "(w := x)",
        "'texto'",
        "1j + x",
        "True + x",
        "None",
        "sin",
        "pi(x)",
        "sin(x, y)",
        "sin(x=1)",
        "sin()",
        "sin(*x)",
        "x @ y",
        "x // y",
        "x % y",
        "~x",
        "w + 1",
    ],
)
def test_check_rejects_constructs_outside_the_grammar(expression):
    with pytest.raises(ExpressionError):
        check_expression(expression)


@pytest.mark.parametrize("expression", ["9**9**9**9", "1e999 + x", "10**400 + x"])
def test_check_rejects_expressions_that_overflow(expression):
    with pytest.raises(ExpressionError):
        check_expression(expression)
