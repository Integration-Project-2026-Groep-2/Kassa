import importlib


def test_determine_status_thresholds():
    import src.status as st

    assert st._determine_status(0.0, 0.0, 0.0) == 'healthy'
    assert st._determine_status(0.95, 0.0, 0.0) == 'degraded'
    assert st._determine_status(0.0, 0.95, 0.0) == 'degraded'


def test_build_status_xml(monkeypatch):
    import src.status as st
    # force system load zeros
    monkeypatch.setattr(st, '_get_system_load', lambda: (0.0, 0.0, 0.0))
    xml = st._build_status_xml()
    assert b'StatusCheck' in xml and b'serviceId' in xml


def test_get_system_load_no_psutil(monkeypatch):
    import src.status as st
    # simulate ImportError path
    monkeypatch.setitem(__import__('sys').modules, 'psutil', None)
    cpu, mem, disk = st._get_system_load()
    assert cpu == 0.0 and mem == 0.0 and disk == 0.0
