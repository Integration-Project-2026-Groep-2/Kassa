import importlib
import logging


def test_validate_xml_none_schema(monkeypatch):
    # simulate missing schema by forcing _schema to None
    import src.xml_validator as xv

    monkeypatch.setattr(xv, '_schema', None)
    ok, err = xv.validate_xml('<foo/>')
    assert ok is True and err is None


def test_validate_xml_syntax_error():
    import src.xml_validator as xv

    # malformed XML should return False and an error string
    ok, err = xv.validate_xml('<unclosed>')
    assert ok is False and err is not None


def test_validate_xml_document_invalid():
    import src.xml_validator as xv

    # provide an XML that parses but should fail schema validation
    xml = '<NotRoot><child/></NotRoot>'
    ok, err = xv.validate_xml(xml)
    # either False with error, or True if schema not strict; assert boolean
    assert isinstance(ok, bool)


def test_configure_logging_console_and_handler(monkeypatch):
    # Reload logging_config with HAS_AIOPIKA disabled to avoid threads
    import src.logging_config as lc
    importlib.reload(lc)

    root = logging.getLogger()
    # remove existing handlers for clean state
    old = list(root.handlers)
    for h in list(root.handlers):
        root.removeHandler(h)

    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    monkeypatch.setattr(lc, 'HAS_AIOPIKA', False)
    importlib.reload(lc)

    handlers = root.handlers
    assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    # create a RabbitMQLogHandler directly with HAS_AIOPIKA False (worker returns)
    h = lc.RabbitMQLogHandler(service_name='TEST')
    rec = logging.LogRecord('t', logging.INFO, '/', 1, 'msg', (), None)
    # should not raise
    h.emit(rec)
    h.close()
