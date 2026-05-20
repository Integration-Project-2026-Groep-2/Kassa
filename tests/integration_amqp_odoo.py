import os
import pytest

# Skip integration tests by default — enable by setting RUN_INTEGRATION=1 in the environment.
if os.environ.get("RUN_INTEGRATION", "0") != "1":
    pytest.skip("Integration tests skipped by default; set RUN_INTEGRATION=1 to run.", allow_module_level=True)


def test_placeholder_integration():
    # TODO: implement real integration using testcontainers (RabbitMQ + Fake Odoo)
    assert True
