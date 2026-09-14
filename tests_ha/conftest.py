"""Exercise the integration with Home Assistant itself."""
import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield
