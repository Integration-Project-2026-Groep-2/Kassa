import asyncio
import pytest


def test_parse_and_validate_invalid(monkeypatch):
    import src.receiver as rc

    # simulate validate_xml returning False
    monkeypatch.setattr(rc, 'validate_xml', lambda s: (False, 'err'))
    res = rc._parse_and_validate(b'<x/>', 'C')
    assert res is None


def test_parse_and_validate_ok(monkeypatch):
    import src.receiver as rc
    from lxml import etree

    monkeypatch.setattr(rc, 'validate_xml', lambda s: (True, None))
    el = rc._parse_and_validate(b'<Root><a>1</a></Root>', 'C')
    assert isinstance(el, etree._Element)


@pytest.mark.asyncio
async def test_on_warning_handler(monkeypatch):
    import src.receiver as rc

    class FakeMsg:
        def __init__(self, body):
            self.body = body

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def process(self):
            return self

    # invalid body -> should return early without exception
    monkeypatch.setattr(rc, 'validate_xml', lambda s: (False, 'bad'))
    await rc.on_warning(FakeMsg(b'<bad/>'))
