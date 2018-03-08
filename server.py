from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import broadlink, configparser
import sys, getopt
import time, binascii
import netaddr
import settings
import signal
from os import path
from Crypto.Cipher import AES

class Server(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):

        if 'favicon' in self.path:
            return False

        self._set_headers()

        if len(self.path.split('/')) < 2:
            self.wfile.write("Failed")
            return True

        deviceName = self.path.split('/')[1]

        if not settingsFile.has_section(deviceName):
            self.wfile.write("Failed: Device '%s' is not exists in settings.ini" % deviceName)
            return True

        devIPAddress = settingsFile.get(deviceName, 'IPAddress')
        devPort = settingsFile.get(deviceName, 'Port')
        devMACAddress = settingsFile.get(deviceName, 'MACAddress')

        if devIPAddress.strip() == '':
            self.wfile.write("Device IP address must exist in settings.ini")
            return True

        if devPort.strip() == '':
            self.wfile.write("Device Port must exist in settings.ini")
            return True
        devPort = int(devPort.strip())

        if devMACAddress.strip() == '':
            self.wfile.write("Device MAC address must exist in settings.ini")
            return True
        devMACAddress = netaddr.EUI(devMACAddress)

        if deviceName.find('RM') == 0:
            return self.get_RMDevice(deviceName, devIPAddress, devPort, devMACAddress)

        if deviceName.find('SP2') == 0:
            return self.get_SP2Device(deviceName, devIPAddress, devPort, devMACAddress)

        elif 'a1'  in self.path:
            sensor = self.path.split('/')[2]
            result = getA1Sensor(sensor)
            if result == False:
                self.wfile.write("Failed getting A1 data")
            else:
                if sensor == 'temperature' or sensor == 'humidity':
                    self.wfile.write('''{ "%s": %s }''' % (sensor, result))
                else:
                    self.wfile.write('''{ "%s": "%s" }''' % (sensor, result))
        else:
            self.wfile.write("Failed")

    def get_RMDevice(self, deviceName, rmIPAddress, rmPort, rmMACAddress):
        if len(self.path.split('/')) < 4:
            self.wfile.write("Failed")
            return True
        actionName = self.path.split('/')[2]
        commandName = self.path.split('/')[3]

        if 'learnCommand' in actionName:
            result = learnCommand(rmIPAddress, rmPort, rmMACAddress, commandName)
            if result == False:
                self.wfile.write("Failed: No command learned")
            else:
                self.wfile.write("Learned: %s" % commandName)

        elif 'sendCommand' in actionName:
            if 'on' in commandName or 'off' in commandName:
                status = commandName.rsplit('o', 1)[1]
                realcommandName = commandName.rsplit('o', 1)[0]
                print(status, realcommandName)
                if 'n' in status:
                    setStatus(realcommandName, '1', True)
                elif 'ff' in status:
                    setStatus(realcommandName, '0', True)
            result = sendCommand(rmIPAddress, rmPort, rmMACAddress, commandName)
            if result == False:
                self.wfile.write("Failed: Unknonwn command")
            else:
                self.wfile.write("Sent: %s" % commandName)

        elif 'getStatus' in actionName:
            if 'temp' in commandName:
                result = getTempRM(rmIPAddress, rmPort, rmMACAddress)
                if result == False:
                    self.wfile.write("Failed: Cannot get temperature")
                else:
                    self.wfile.write('''{ "temperature": %s } ''' % result)
            else:
                status = getStatus(commandName)
                if (status):
                    self.wfile.write(status)
                else:
                    self.wfile.write("Failed: Unknown command")

        elif 'setStatus' in self.path:
            commandName = self.path.split('/')[2]
            status = self.path.split('/')[3]
            result = setStatus(commandName, status)
            print('Setting status %s of %s' % (commandName, status))
            if (result):
                self.wfile.write("Set status of %s to %s" % (commandName, status))
            else:
                self.wfile.write("Failed: Unknown command")

        else:
            self.wfile.write("Failed: Unknown action")

    def get_SP2Device(self, deviceName, devIPAddress, devPort, devMACAddress):
        if len(self.path.split('/')) < 3:
            self.wfile.write("Failed")
            return True
        commandName = self.path.split('/')[2]

        device = broadlink.sp2((devIPAddress, devPort), devMACAddress)
        try:
            device.auth()
        except Exception, msg:
            self.wfile.write("Failed: Connect to device timed out")
            return True

        try:
            if 'setPowerOn' in commandName:
                device.set_power(True)
                self.wfile.write("Success")

            elif 'setPowerOff' in commandName:
                device.set_power(False)
                self.wfile.write("Success")

            elif 'checkPower' in commandName:
                state = device.check_power()
                self.wfile.write('''{ "%s": "%s" }''' % ("state", state))

            elif 'getEnergy' in commandName:
                energy = device.get_energy()
                self.wfile.write('''{ "%s": "%s" }''' % ("energy", energy))

            else:
                self.wfile.write("Failed: Unknown command")
            return True

        except Exception, msg:
            self.wfile.write("Failed: Send command to device failed")
            return True


serverPort = ''

def sendCommand(rmIPAddress, rmPort, rmMACAddress, commandName):
    device = broadlink.rm((rmIPAddress, rmPort), rmMACAddress)
    try:
        device.auth()
    except Exception, msg:
        print "Connect to device timed out.."
        return False

    deviceKey = device.key
    deviceIV = device.iv

    if settingsFile.has_option('Commands', commandName):
        commandFromSettings = settingsFile.get('Commands', commandName)
    else:
        return False

    print('sending command %s' % commandName)
    if commandFromSettings.strip() != '':
        decodedCommand = binascii.unhexlify(commandFromSettings)
        AESEncryption = AES.new(str(deviceKey), AES.MODE_CBC, str(deviceIV))
        encodedCommand = AESEncryption.encrypt(str(decodedCommand))
        
        finalCommand = encodedCommand[0x04:]    
        
        #signal.signal(signal.SIGALRM, signal_handler)
        #signal.alarm(4)   # Ten seconds
        try:
            device.send_data(finalCommand)
        except Exception, msg:
            print "Probably timed out.."
            return True

def learnCommand(rmIPAddress, rmPort, rmMACAddress, commandName):
    device = broadlink.rm((rmIPAddress, rmPort), rmMACAddress)
    try:
        device.auth()
    except Exception, msg:
        print "Connect to device failed"
        return False

    deviceKey = device.key
    deviceIV = device.iv

    try:
        device.enter_learning()
        time.sleep(RealTimeout)
        LearnedCommand = device.check_data()
    except Exception, msg:
        print "Learn command failed"
        return False

    if LearnedCommand is None:
        print('Command not received')
        return False

    AdditionalData = bytearray([0x00, 0x00, 0x00, 0x00])    
    finalCommand = AdditionalData + LearnedCommand

    AESEncryption = AES.new(str(deviceKey), AES.MODE_CBC, str(deviceIV))
    decodedCommand = binascii.hexlify(AESEncryption.decrypt(str(finalCommand)))

    broadlinkControlIniFile = open(path.join(settings.applicationDir, 'settings.ini'), 'w')    
    settingsFile.set('Commands', commandName, decodedCommand)
    settingsFile.write(broadlinkControlIniFile)
    broadlinkControlIniFile.close()
    return True

def setStatus(commandName, status, exist = False):
    if exist:
        broadlinkControlIniFile = open(path.join(settings.applicationDir, 'settings.ini'), 'w')    
        settingsFile.set('Status', commandName, status)
        settingsFile.write(broadlinkControlIniFile)
        broadlinkControlIniFile.close()
        return True

    if settingsFile.has_option('Status', commandName):
        commandFromSettings = settingsFile.get('Status', commandName)
    else:
        return False
    if commandFromSettings.strip() != '':
        broadlinkControlIniFile = open(path.join(settings.applicationDir, 'settings.ini'), 'w')    
        settingsFile.set('Status', commandName, status)
        settingsFile.write(broadlinkControlIniFile)
        broadlinkControlIniFile.close()
        return True
    else:
        return False

def getStatus(commandName):
    if settingsFile.has_option('Status', commandName):
        status = settingsFile.get('Status', commandName)
        return status
    else:
        return False

def getTempRM(rmIPAddress, rmPort, rmMACAddress):
    device = broadlink.rm((rmIPAddress, rmPort), rmMACAddress)
    device.auth()
    temperature = device.check_temperature()
    if temperature:
        return temperature
    return False 

def getA1Sensor(sensor):
    device = broadlink.a1((A1IPAddress, A1Port), A1MACAddress)
    device.auth()
    result = device.check_sensors()
    if result:
        return result[sensor]
    return False 

def signal_handler(signum, frame):
    print ("HTTP timeout, but the command should be already sent.")
        
def start(server_class=HTTPServer, handler_class=Server, port=serverPort):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print 'Starting broadlink-rest server on port %s ...' % port
    httpd.serve_forever()

if __name__ == "__main__":
    settingsFile = configparser.ConfigParser()
    settingsFile.optionxform = str
    settingsFile.read(settings.settingsINI)

    A1IPAddress = settings.A1IPAddress
    if A1IPAddress.strip() == '':
        print('IP address must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)

    A1Port = settings.A1Port
    if A1Port.strip() == '':
        print('Port must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)
    else:
        A1Port = int(A1Port.strip())

    A1MACAddress = settings.A1MACAddress
    if A1MACAddress.strip() == '':
        print('MAC address must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)
    else:
        A1MACAddress = netaddr.EUI(A1MACAddress)

    RealTimeout = settings.Timeout
    if RealTimeout.strip() == '':
        print('Timeout must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)
    else:
        RealTimeout = int(RealTimeout.strip())    


    if settingsFile.has_option('General', 'serverPort'):
        serverPort = int(settingsFile.get('General', 'serverPort'))
    else:
        serverPort = 8080

    start(port=serverPort)
