from __future__ import annotations

from firefighter.api.renderer import CSVRenderer


def test_tablize_hides_headers_when_labels_hidden() -> None:
    renderer = CSVRenderer()
    rows = list(renderer.tablize([{"id": 1, "value": "foo"}], labels="__hidden__"))

    assert rows == [[1, "foo"]]


def test_tablize_applies_custom_labels() -> None:
    renderer = CSVRenderer()
    rows = list(
        renderer.tablize(
            [{"a": 1, "b": 2}],
            header=["b", "a"],
            labels={"a": "Column A", "b": "Column B"},
        )
    )

    assert rows[0] == ["Column B", "Column A"]
    assert rows[1] == [2, 1]


def test_get_headers_preserves_explicit_order_without_wildcards() -> None:
    renderer = CSVRenderer()
    _, header = renderer._get_headers([{"x": 1, "y": 2}], ["y", "x"])

    assert header == ["y", "x"]


def test_get_headers_expands_wildcards_sorted() -> None:
    renderer = CSVRenderer()
    _, header = renderer._get_headers(
        [{"fixed": 1, "meta.foo.value": 10, "meta.bar.value": 20}],
        ["fixed", "meta.*.value"],
    )

    assert header == ["fixed", "meta.bar.value", "meta.foo.value"]
