from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from common.environment_config import Config

class Instance():
    def __init__(self) -> None:
      self.driver = Config.driver
      self.backButton = None
      self.driver.implicitly_wait(10)
      self.variableInitialization()
    
    #Variable intilization function
    def variableInitialization(self):
      self.backButton = self.driver.find_element(By.XPATH, "//span[contains(text(),'All Infrastructure')]")
      
    def countOfList(self):
      count = 0
      try:
        #UI is displayed or loading page is there or No data found page
        self.driver.find_element(By.XPATH,"//div[@data-test='card-header']/following-sibling::div")
        try:
          #Is table is displayed or error in signalFlow query
          self.driver.find_element(By.CSS_SELECTOR, "table[role='table']")
          #Check if the groupBy is None or not
          groupBySelected = self.driver.find_element(By.XPATH,"//div[@data-test='card-header']//div[@data-test='controls']/button[@data-test='select']//span[@data-test='label']")
          if groupBySelected.text != 'none':
            groupBySelected.click()
            noneOption = self.driver.find_element(By.XPATH,"//div[@data-test='menu']/button[1]")
            noneOption.click()
            
          try:
            #Check wether Pagination is there or not
            lastPageBtn = self.driver.find_element(By.XPATH,"//div[@data-test='paginator']/button[@data-test='next']/preceding::button[1]")
            #Counting the rows in list - Each page have 10 rows max
            count = (int(lastPageBtn.text) - 1) * 10
            lastPageBtn.click()
            #Counting the rows in last page
            rows = self.driver.find_elements(By.XPATH,"//table[@role='table']/tbody/tr")
            noOfRows = len(rows)
            count = count + noOfRows
            return int(count)
          #If Pagination is not there and no is 10 or below
          except NoSuchElementException:
            rows = self.driver.find_elements(By.XPATH,"//table[@role='table']/tbody/tr")
            noOfRows = len(rows)
            count = count + noOfRows
            return int(count)
        #Table didn't loaded - problem with signalFlow query in navigator json
        except NoSuchElementException:
          return "Table didn't loaded"
      #No Data found message seen. Query is wrong
      except NoSuchElementException:
        return "No data in this navigator"
        
    def countOfFirstChart(self):
      try:
        #Collecting first Chart and its count dispalyed
        firstChartCount = self.driver.find_element(By.XPATH,"//div[@data-test='card']/div[@data-test='body']//ul/li//div[contains(@class,'single-value-value')][1]").text
        firstChartCount = firstChartCount.replace(',','')
        return int(firstChartCount)
      #First chart is not signal value
      except:
        return "No Single value chart"
    
    #Going back to aggregated Page function
    def goToInfraAggPage(self):
      self.backButton.click()