import ast

from app.services.complexity_engine import compute_function_complexities, function_complexity

# Each expected value below was hand-derived from McCabe's formula
# (M = decision points + 1, equivalently E - N + 2 on the actual CFG this
# module builds) before running the code, then checked against it - not the
# other way around.


def _complexity_of(source: str) -> int:
    tree = ast.parse(source)
    func = tree.body[0]
    return function_complexity(func)


def test_straight_line_function_has_complexity_one():
    assert _complexity_of("def foo(x):\n    y = x + 1\n    return y\n") == 1


def test_single_if_without_else():
    assert _complexity_of("def foo(x):\n    if x > 0:\n        return 1\n    return 2\n") == 2


def test_if_else_is_still_one_decision_point():
    # The else branch adds no extra decision - it's the same branch's false path.
    src = "def foo(x):\n    if x > 0:\n        return 1\n    else:\n        return 2\n"
    assert _complexity_of(src) == 2


def test_elif_is_a_second_decision_point():
    src = (
        "def foo(x):\n"
        "    if x > 0:\n"
        "        return 1\n"
        "    elif x < 0:\n"
        "        return 2\n"
        "    else:\n"
        "        return 3\n"
    )
    assert _complexity_of(src) == 3


def test_nested_if_elif():
    src = (
        "def foo(x, y):\n"
        "    if x > 0:\n"
        "        if y > 0:\n"
        "            return 1\n"
        "        else:\n"
        "            return 2\n"
        "    elif x < 0:\n"
        "        return 3\n"
        "    return 4\n"
    )
    assert _complexity_of(src) == 4


def test_for_loop_adds_one_decision_point():
    src = "def foo(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n"
    assert _complexity_of(src) == 2


def test_boolean_and_adds_its_own_decision_point():
    src = "def foo(x, y):\n    if x > 0 and y > 0:\n        return 1\n    return 2\n"
    assert _complexity_of(src) == 3


def test_break_inside_a_loop():
    src = (
        "def foo(items):\n"
        "    for item in items:\n"
        "        if item < 0:\n"
        "            break\n"
        "    return items\n"
    )
    assert _complexity_of(src) == 3


def test_try_except_adds_a_decision_point_per_handler():
    src = "def foo(x):\n    try:\n        return 1 / x\n    except ZeroDivisionError:\n        return 0\n"
    assert _complexity_of(src) == 2


def test_compute_function_complexities_from_a_diff_patch():
    patch = (
        "@@ -1,2 +1,7 @@\n"
        " import os\n"
        "+def risky(x):\n"
        "+    if x > 0:\n"
        "+        return 1\n"
        "+    elif x < 0:\n"
        "+        return 2\n"
        "+    return 3\n"
    )
    result = compute_function_complexities(patch)
    assert result == {"risky": 3}


def test_unparseable_fragment_returns_empty_dict_not_an_error():
    patch = "@@ -1,1 +1,2 @@\n def foo(\n+    if x:\n"
    assert compute_function_complexities(patch) == {}
