import configparser
from os import path

applicationDir = path.dirname(path.abspath(__file__))
settingsINI = path.join(applicationDir, 'settings.ini')

settings = configparser.ConfigParser()
settings.read(settingsINI)

Timeout = settings.get('General', 'Timeout')


A1IPAddress = settings.get('BroadlinkA1', 'IPAddress')
A1Port = settings.get('BroadlinkA1', 'Port')
A1MACAddress = settings.get('BroadlinkA1', 'MACAddress')
