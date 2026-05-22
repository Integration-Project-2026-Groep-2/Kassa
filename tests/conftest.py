import sys
import types
import importlib
from pathlib import Path
import pytest

# Ensure the repository root is on sys.path so imports like `src.xml_validator`
# work both locally and in CI runners where the working directory may differ.
repo_root = Path(__file__).resolve().parents[1]
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

# Shared test setup: provide lightweight stubs and import aliases so tests
# can import top-level modules (`messaging`, `odoo_integration`, `connection`, etc.)

# settings stub
settings = types.ModuleType("settings")
settings.RABBIT_HOST = "localhost"
settings.RABBIT_PORT = 5672
settings.RABBIT_USER = "guest"
settings.RABBIT_PASSWORD = "guest"
settings.RABBIT_VHOST = "/"
sys.modules.setdefault("settings", settings)

# models.user stub (used by several modules)
models = types.ModuleType("models")
user_mod = types.ModuleType("models.user")

class _FakeUser:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def validate(self):
        return True, None

    @staticmethod
    def _is_valid_uuid(val):
        return True

user_mod.User = _FakeUser
user_mod.UserRole = object
sys.modules.setdefault("models", models)
sys.modules.setdefault("models.user", user_mod)

# connection alias to src.connection (uses settings stub above)
try:
    src_conn = importlib.import_module("src.connection")
    sys.modules.setdefault("connection", src_conn)
except Exception:
    # fallback: provide a minimal connection stub
    conn_mod = types.ModuleType("connection")
    class _Mgr:
        def __init__(self):
            self.channel = None
        def connect(self, max_retries=None):
            return None
        def close(self):
            return None
    conn_mod.RabbitManager = _Mgr
    sys.modules.setdefault("connection", conn_mod)

# xml_validator alias
try:
    xml_mod = importlib.import_module("src.xml_validator")
    sys.modules.setdefault("xml_validator", xml_mod)
except Exception:
    sys.modules.setdefault("xml_validator", types.ModuleType("xml_validator"))

# Expose a package-like `messaging` so tests can import `messaging.user_consumer`
messaging_pkg = types.ModuleType("messaging")
messaging_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "messaging")]
sys.modules["messaging"] = messaging_pkg
try:
    sys.modules.setdefault("messaging.message_builders", importlib.import_module("src.messaging.message_builders"))
    sys.modules.setdefault("messaging.producer", importlib.import_module("src.messaging.producer"))
    sys.modules.setdefault("messaging.user_consumer", importlib.import_module("src.messaging.user_consumer"))
except Exception:
    pass

# Map odoo_integration submodules
odoo_pkg = types.ModuleType("odoo_integration")
odoo_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "odoo_integration")]
sys.modules.setdefault("odoo_integration", odoo_pkg)
try:
    sys.modules.setdefault("odoo_integration.user_repository", importlib.import_module("src.odoo_integration.user_repository"))
    sys.modules.setdefault("odoo_integration.odoo_connection", importlib.import_module("src.odoo_integration.odoo_connection"))
except Exception:
    pass


@pytest.fixture(autouse=True)
def reload_core_modules():
    """Reload core modules before each test to avoid cross-test mutations."""
    try:
        importlib.reload(importlib.import_module("src.xml_validator"))
    except Exception:
        pass
    try:
        # reload both the src and messaging module entries and align them
        if "src.messaging.user_consumer" in sys.modules:
            m = importlib.reload(sys.modules["src.messaging.user_consumer"])
            sys.modules["messaging.user_consumer"] = m
        elif "messaging.user_consumer" in sys.modules:
            m = importlib.reload(sys.modules["messaging.user_consumer"])
            sys.modules["src.messaging.user_consumer"] = m
        # ensure the module uses the up-to-date xml_validator.validate_xml symbol
        try:
            import src.xml_validator as _xv
            if "messaging.user_consumer" in sys.modules:
                sys.modules["messaging.user_consumer"].validate_xml = _xv.validate_xml
        except Exception:
            pass
    except Exception:
        pass
    yield
