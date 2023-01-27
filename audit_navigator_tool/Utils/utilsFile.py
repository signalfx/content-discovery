import json
from pathlib import Path

with open(str(Path(__file__).parent.parent.joinpath("Utils", "config.json"))) as configFile:
    config = json.load(configFile)


def getEmail():
    return config['email']


def getPassword():
    return config['password']


def headless():
    return config['headless']


def getUrl():
    return config['url']


def getNavigatorName():
    return config['navigatorName']


def getCategoryName():
    return config['catgoryName']


def getBrowser():
    return config['browser']
