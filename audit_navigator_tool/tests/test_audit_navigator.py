import pytest

from PageObjects.Infrastructure import Navigators
from PageObjects.LoginPage import LoginPage
from pathlib import Path
import json


#TEST CASE

# 1. Login with username and password
# 2. For all navigators if populating data
#     1. Store the value that card is displaying
#     2. Take screenshot of that card
#     3. Click that card
#     4. If pagination is there, Store last page number
#     5. Click last page number
#     6. Count the list of instances on that page and store the count
#     7. Multiply 10 * (last page number - 1) + count in Step 6
#     8. Take screenshot of that list
#     9. If pagination is not there, step 5
#     10. Store the value displayed in 1st chart of dashboard displayed below the instances
#     11. Take screenshot of that chart
#     12. Compare all three values and it should be same
#     13. Append the findings in JSON file.
# 3. Generate report of step 4
# 4. Logout


@pytest.mark.usefixtures("browser_setup")
def test_audit_navigatoravigator():
  LoginPage().loginInIntoOrg()
  report = Navigators().getNavigators()
  print(report[0])
  #Writing the report generated into file
  conclusion = {"Total Navigators": report[1],"Test Navigators": report[2],"Reviews": report[0]}
  with open((str(Path(__file__).parent.parent.joinpath("Reports", "report.json"))),"w") as f:
    f.write(json.dumps(conclusion))