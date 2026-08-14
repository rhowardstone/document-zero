"""The page escapes at the point of DOM insertion. This tests that it does.

Escaping used to happen in ledger/render.py, and index.html assigned the result
through innerHTML on the contract that the projection had escaped every field.
That contract failed twice — once for record fields, once for the hold reason —
and each failure was stored DOM XSS from scraped text.

The guarantee now lives in the page: every ledger string is interpolated through
H(), and H() escapes. That is a stronger guarantee because it cannot be
forgotten field by field — a template literal cannot interpolate a value without
calling the function.

But a guarantee in a language nothing tests is not a guarantee, so these tests
extract the real H() from index.html and run it, and then check that no ledger
value reaches a template without it.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parents[1] / "index.html"
node = shutil.which("node")
needs_node = pytest.mark.skipif(not node, reason="node not available")


def _extract(fn_name: str) -> str:
    """Pull a const arrow function out of index.html by name."""
    src = INDEX.read_text(encoding="utf-8")
    m = re.search(rf"^const {fn_name} = .*?;$", src, re.M | re.S)
    assert m, f"{fn_name} not found in index.html"
    return m.group(0)


def run_js(body: str):
    out = subprocess.run([node, "-e", body], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
@pytest.mark.parametrize("payload,must_not_contain", [
    ('<img src=x onerror="alert(1)">', "<img"),
    ("</script><script>alert(2)</script>", "<script"),
    ('"><svg onload=alert(3)>', "<svg"),
    ("' onmouseover='alert(4)", "onmouseover='"),
    ('" autofocus onfocus="alert(5)', 'onfocus="'),
    ("<iframe src=javascript:alert(6)>", "<iframe"),
])
def test_the_pages_own_escaper_neutralises_real_payloads(payload, must_not_contain):
    got = run_js(_extract("H") + f"\nconsole.log(JSON.stringify(H({json.dumps(payload)})));")
    assert must_not_contain not in got, got
    assert "<" not in got and ">" not in got


@needs_node
def test_the_escaper_is_not_the_identity_function():
    """It was, for the whole first version of this page."""
    assert run_js(_extract("H") + '\nconsole.log(JSON.stringify(H("<b>")));') == "&lt;b&gt;"


@needs_node
def test_ampersand_is_escaped_first_so_entities_are_not_forged():
    """Escaping < before & would turn "&lt;" typed by a source into a real tag."""
    assert run_js(_extract("H") + '\nconsole.log(JSON.stringify(H("&lt;script&gt;")));') \
        == "&amp;lt;script&amp;gt;"


@needs_node
def test_null_and_undefined_do_not_render_as_the_word_null():
    for v in ("null", "undefined"):
        assert run_js(_extract("H") + f'\nconsole.log(JSON.stringify(H({v})));') == ""


def test_every_ledger_interpolation_in_the_page_goes_through_the_escaper():
    """A structural check: find `${...}` holes that read a ledger object
    directly without H()/t(). This is what would have caught both XSS bugs."""
    src = INDEX.read_text(encoding="utf-8")
    # Only look inside template literals in the render functions.
    holes = re.findall(r"\$\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", src)
    bad = []
    for h in holes:
        expr = h.strip()
        # Names bound to LEDGER objects. `row` and `rt` are page-constructed
        # (diff rows and route descriptors) and are deliberately excluded: their
        # ledger-derived pieces were escaped when the object was built.
        if not re.search(r"\b(?:i|b|c|q|x|s|e|it|rec)\.[a-zA-Z_]", expr):
            continue
        if "H(" in expr or "t(" in expr:
            continue                      # escaped
        # Numeric, boolean and length reads cannot carry markup.
        if re.search(r"\.(?:length|count|corroboration|unchanged|claims_standing|"
                     r"confidence|rounds|publish)\b", expr):
            continue
        if re.match(r"^[a-z]+\.(?:id|kind|status)\b", expr):
            continue                      # slugs, and they go through t() anyway
        bad.append(expr[:90])
    assert not bad, "unescaped ledger interpolation(s):\n" + "\n".join(bad)
