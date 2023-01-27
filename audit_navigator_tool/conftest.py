import pytest
from common.environment_config import Config
from Components.driverInitilization import Browser


@pytest.fixture(scope="function")
def browser_setup():
    Config.driver = Browser().initializeDriver()

