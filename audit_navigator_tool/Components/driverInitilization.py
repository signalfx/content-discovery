from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from Utils import utilsFile


class Browser:

    def __init__(self) -> None:
        self.driver = None
        self.browser = None

    def initializeDriver(self):
        self.browser = Service(utilsFile.getBrowser())
        self.driver = webdriver.Chrome(service=self.browser)
        self.driver.implicitly_wait(10)
        self.driver.get(utilsFile.getUrl())
        self.driver.maximize_window()
        return self.driver

    def getDriver(self):
        return self.driver

    def closeDriver(self):
        self.driver.close()
