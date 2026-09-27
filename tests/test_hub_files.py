import pytest

hub = pytest.importorskip("zoya.hub")


@pytest.mark.parametrize(
    "path",
    ["/../../etc/passwd", "/appicon/..%2F..%2Fetc", "/appicon/%2FSystem%2FLibrary", "/hub.py"],
)
def test_the_hub_serves_nothing_outside_its_files(path) -> None:  # noqa: ANN001
    assert hub._resource(path) is None


def test_an_app_icon_is_a_small_png() -> None:
    body, kind = hub._resource("/appicon/Finder")
    assert kind == "image/png" and body.startswith(b"\x89PNG") and len(body) < 64_000
