import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from common.environment_config import Config
from PageObjects.ServiceNavigator import Instance
import re


class Navigators():
    def __init__(self) -> None:
      self.driver = Config.driver
      self.navigatorCard = None
      self.dashboardNavigatorName = []
      self.report = []
      self.driver.implicitly_wait(10)
      self.variableInitialization()
      
    #Variable Initiliazition function
    def variableInitialization(self):
      time.sleep(25)
      WebDriverWait(self.driver, 50).until(lambda x: x.find_element(By.CSS_SELECTOR, "input[placeholder='Search']"))
      self.navigatorCard = self.driver.find_elements(By.XPATH, "//div[@data-test='header']/parent::div")
      dashboardTilesNavigatorNames = self.driver.find_elements(By.XPATH,"//span[@data-test='tooltip']/span[@data-test='toggle']/div/div/*[local-name()='svg']/*[local-name()='path']/../../../../../../..//div[@data-test='header']")
      for dashboardNavName in dashboardTilesNavigatorNames:
        print(dashboardNavName.text)
        self.dashboardNavigatorName.append(dashboardNavName.text)
      
    #Get all the navigators
    def getNavigators(self):
      navigatorTile = []
      count = 0
      dbcnt = 0
      print(len(self.navigatorCard))
      for name in self.navigatorCard:
        count+=1
        navCardDisplayedTexts = name.text.split("\n")
        #Ignore the dashbaords on navigator page navigator tiles, They redirect to dashboards page. So no need to audit them
        if navCardDisplayedTexts[0] in self.dashboardNavigatorName:
          dbcnt+=1
          continue
        # print(navCardDisplayedTexts[0])
        navigatorTile.append(navCardDisplayedTexts[0])
      print("db Cnt ",dbcnt)
      print("Count ",count)
      print(len(navigatorTile))
      print(navigatorTile)
      self.navigatorCard = self.driver.find_elements(By.CLASS_NAME, "//div[@data-test='header']/parent::div")
      #   #Accept the navigators with some count on the tile
      #   if len(navCardDisplayedTexts) >= 3:
      #     #Above 999 the data count was including , in number so regex
      #     pattern = re.compile("^([0-9],?)+$")
      #     if pattern.match(navCardDisplayedTexts[1]) or pattern.match(navCardDisplayedTexts[2]):
      #       navCardDisplayedTexts[2] = navCardDisplayedTexts[2].replace(',','')
      #       print(navCardDisplayedTexts[0])
      #       navigatorTile[navCardDisplayedTexts[0]] = navCardDisplayedTexts[2]
      
      # # listOfNavigators = ["Hosts","Zookeeper","Couchbase Cluster","Couchbase Nodes","Elasticsearch clusters","Elasticsearch nodes","Microsoft SQL Databases","Microsoft SQL Servers","Mongo DB Hosts","MySQL Hosts","Oracle DB instances","Redis Instances","RabbitMQ Nodes","JMX (collectd)","Apache Web Servers","Windows IIS Servers"]
      # for navName in navigatorTile:
      #   # print(navName)
      #   # if navName not in listOfNavigators:
      #   #   continue
      #   #Format for JSON result report
      #   message = {
      #     "Navigator": "",
      #     "Aggregated Count": "",
      #     "List Count": "",
      #     "First Chart Count": "",
      #     "Conclusion": ""}
      #   # count = count + 1
      #   message["Navigator"] = navName
      #   navigatorTile[navName] = int(navigatorTile[navName])
      #   message["Aggregated Count"] = navigatorTile[navName]
      #   # if count == 2:
      #   #   break
      #   self.driver.find_element(By.XPATH,"//div[text()='"+ navName +"']").click()
      #   time.sleep(3)
        
      #   #Checking if the returned value is numeric or error message
      #   listCount = Instance().countOfList()
      #   if type(listCount) == int:
      #     message["List Count"] = listCount
      #   else:
      #     message["List Count"] = "-"
      #     message["Conclusion"] = listCount
        
      #   #Getting the count fo First chart in dashboard if it is single value chart
      #   chartCount = Instance().countOfFirstChart()
      #   if type(chartCount) == int:
      #     message["First Chart Count"] = chartCount
      #   else:
      #     message["First Chart Count"] = "-"
      #     #Checking if listCount is alredy having error or not
      #     if message["Conclusion"] != "":
      #       message["Conclusion"] = " and " + chartCount
      #     else:
      #       message["Conclusion"] = chartCount
        
      #   #Comparing all the counts
      #   if message["Conclusion"] == "":
      #     if navigatorTile[navName] == listCount:
      #       if listCount == chartCount:
      #         message["Conclusion"] = "Match"
      #       else:
      #         message["Conclusion"] = "List and Chart doesn't match"
      #     else:
      #       message["Conclusion"] = "Tile and List doesn't match"
            
      #   #Coming back to Aggregated page
      #   Instance().goToInfraAggPage()
      #   time.sleep(3)
            
      #   #Printing the message which will be appending in the report
      #   print(message)
      #   self.report.append(message)
      # return [self.report,len(self.navigatorCard),len(navigatorTile)]