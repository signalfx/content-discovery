from Utils import utilsFile
from selenium.webdriver.common.by import By
from common.environment_config import Config
from selenium.webdriver.support.wait import WebDriverWait


class LoginPage:
    def __init__(self) -> None:
      # Initializing driver
      self.driver = Config.driver
      self.signInBtn = None
      self.emailTextBox = None
      self.passwordTextBox = None
      self.driver.implicitly_wait(10)
      self.variableInitialization()

    #Checking the page is loaded or not
    def loginPageIsLoaded(self):
      loginTitle = self.driver.title
      if loginTitle == 'Login':
        return True
      
    #Initializing the variables
    def variableInitialization(self):
      WebDriverWait(self.driver, 20).until(lambda x: x.find_element(By.XPATH, "//div[@class='login-footer']"))
      loginFooter = self.driver.find_element(By.XPATH, "//div[@class='login-footer']")

      # Checking if it is on sign in page or at different page with other sign in options
      if loginFooter.text == "Sign in with your Splunk Observability Cloud username & password":
          loginFooter.click()

      #Waiting for Email input field is accessible
      WebDriverWait(self.driver, 50).until(lambda x: x.find_element(By.XPATH, "//input[@name='email']"))
      
      self.signInBtn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
      self.emailTextBox = self.driver.find_element(By.XPATH, "//input[@name='email']")
      self.passwordTextBox = self.driver.find_element(By.XPATH, "//input[@name='password']")
      
    #Adding email and password into the inputbox
    def signInIntoOrg(self, email, password):
      # Clearing the emailField and adding the email
      self.emailTextBox.clear()
      self.emailTextBox.send_keys(email)

      # Clearing the passwordField and adding the password
      self.passwordTextBox.clear()
      self.passwordTextBox.send_keys(password)

      # Clicking SignInButton
      self.signInBtn.click()
      
    #Logging into the organization
    def loginInIntoOrg(self):
      if self.loginPageIsLoaded():
        self.signInIntoOrg(utilsFile.getEmail(), utilsFile.getPassword())
      else:
        print("Check URL")
