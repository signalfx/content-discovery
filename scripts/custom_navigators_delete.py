import requests
import argparse


class CustomNavigatorDelete:
    """
    Custom navigator deletion script.
    """
    def __init__(self, token, realm):
        self.org_token = token
        self.realm = realm
        self.generic_nav_url = "https://{}.signalfx.com/v2/navigator{}"
        if self.realm == "lab0":
            self.url_nav_get = self.generic_nav_url.format("o11ytest.lab0", "?sites=o11y&sites=o11yandsignalview&limit=1000")
            self.url_nav_del = self.generic_nav_url.format("o11ytest.lab0", "/{}")
        else:
            self.url_nav_get = self.generic_nav_url.format("app", "?sites=o11y&sites=o11yandsignalview&limit=1000")
            self.url_nav_del = self.generic_nav_url.format("app", "/{}")

    def list_all_navigators(self):
        payload = {}
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'x-sf-token': self.org_token
        }
        response = requests.request("GET", self.url_nav_get, headers=headers, data=payload)
        return response.json()

    def delete_all_custom_navigators_from_org(self):
        nav = self.list_all_navigators()
        nav_data = nav.get("results")
        # print(nav_data)
        cnt = 0
        for data in nav_data:
            uimodel_id = data["uiModel"]["id"]
            if (data.get("importOf", None) is None or data.get("importDetails", None) is None):
                delete_nav_id = data["id"]
                print(data["ownerScope"], "  ", data["uiModel"]["o11yProductName"], "  ", delete_nav_id, " ", data["navigatorCategory"])

                url = self.url_nav_del.format(f"{delete_nav_id}?forceDelete=True")
                payload = {}
                headers = {
                    'X-SF-TOKEN': self.org_token
                }
                response = requests.request("DELETE", url, headers=headers, data=payload)
                print(response.status_code)
                cnt += 1
        print("Total number of customer navigators with \"importOf\" key not present in json :", cnt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Example argument parser")
    parser.add_argument("--token", help="X-SF-TOKEN for org.", default="")
    parser.add_argument("--realm", help="Realm code. e.g lab0, us0, us1", default="us0")
    args = parser.parse_args()
    custom_navigators_delete = CustomNavigatorDelete(token=args.token, realm=args.realm)
    custom_navigators_delete.delete_all_custom_navigators_from_org()
