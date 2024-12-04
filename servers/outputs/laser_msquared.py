# -*- coding: utf-8 -*-
"""
siv_resonant_laser

Created on Thu Dec  7 10:16:19 2023

@author: wu

### BEGIN NODE INFO
[info]
name = laser_msquared
version = 1.0
description = 

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""
from labrad.server import LabradServer
from labrad.server import setting
import socket
import json
import logging
from twisted.internet.defer import ensureDeferred

class laserMsquared(LabradServer):
    name = "laser_msquared"
    pc_name = socket.gethostname()
    
    def initServer(self):
        # filename = (
        #     "E:/Shared drives/Kolkowitz Lab"
        #     " Group/nvdata/pc_{}/labrad_logging/{}.log"
        # )
        filename = (
            "D:/Choy_Lab/"
            "sivdata/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.task = None
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)
        # self.laser_socket = None
                    
    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "DeviceIDs"])
        p.get(f"{self.name}_ip")
        p.get(f"{self.name}_port")
        result = await p.send()            
        return result["get"]
        
    def on_get_config(self, reg_vals):
        
        logging.info(reg_vals)
        self.laser_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:            
            self.laser_socket.connect((reg_vals[0], int(reg_vals[1])))  
            response = self.start_link( "192.168.1.6",990)
            response_data = json.loads(response.decode('utf-8'))
            # print('Received', repr(response_data)) 
            # if response_data.get("message", {}).get("parameters", {}).get("status") == "ok":
            #     logging.debug("Init complete")
            #     print("Init complete") 
        except Exception as e:
            print(e) 
            logging.info(e)
            del self.laser_socket
      
            # Check if the status is "ok"
            # if response_data.get("message", {}).get("parameters", {}).get("status") == "ok":
                # logging.debug("Init complete")
                # laser_msquared().start_table_tuning(s, 702, 23)
                # laser_msquared().poll_table_tuning(s, 100)
                # poll_wave_m(s, 10)
                # start_fast_scan(s, "resonator_continuous", 5, 10)
                # data = s.recv(1024)
                # print('Received', repr(data))
                
            
    def send_command(self, command, parameters):
        json_cmd = {
            "message": {
                "transmission_id": [parameters.get("transmission_id", 1)],
                "op": command,
                "parameters": parameters
            }
        }
        cmd = json.dumps(json_cmd).encode('utf-8')
        self.laser_socket.sendall(cmd)
        data = self.laser_socket.recv(1024)
        print(f'Received after {command}:', repr(data))
        return data
        
    def start_link(self, ip_address, transmission_id):
        return self.send_command("start_link", {"ip_address": ip_address, "transmission_id": transmission_id})
    
    def ping(self, text, transmission_id):
        self.send_command("ping", {"text_in": text, "transmission_id": transmission_id})
        
    def poll_wave_m(self,transmission_id):
        return self.send_command("poll_wave_m", {"transmission_id": transmission_id})
    
    def set_wave_m(self, wavelength, transmission_id):
        return self.send_command("set_wave_m", {"wavelength": [wavelength], "transmission_id": transmission_id})
    
    @setting(1, wavelength="v[]",transmission_id="i")
    def start_table_tuning(self, c, wavelength, transmission_id):
        return self.send_command("move_wave_t", {"wavelength": [wavelength], "transmission_id": transmission_id})
    
    @setting(2, transmission_id="i")
    def poll_table_tuning(self, c, transmission_id):
        return self.send_command("poll_move_wave_t", {"transmission_id": transmission_id})
    
    @setting(3,setting="i",transmission_id="i")
    # setting: The Etalon tuning range is expressed as a percentage where 100 is full scale.
    def tune_etalon(self, c, setting, transmission_id):
        return self.send_command("tune_etalon", {"setting": [setting],"transmission_id": transmission_id})
    
    @setting(4,setting="i",transmission_id="i")
    # setting: The cavity tuning range is expressed as a percentage where 100 is full scale.
    def tune_cavity(self, c, setting, transmission_id):
        return self.send_command("tune_cavity", {"setting": [setting],"transmission_id": transmission_id})
    
    @setting(5,setting="i",transmission_id="i")
    def tune_fine_cavity(self, c,setting, transmission_id):
        return self.send_command("fine_tune_cavity", {"setting": [setting],"transmission_id": transmission_id})
    
    @setting(6,setting="v",transmission_id="i")
    def tune_resonator(self, c,setting, transmission_id):
        return self.send_command( "tune_resonator", {"setting": [setting],"transmission_id": transmission_id})
    
    @setting(7,setting="v",transmission_id="i")
    def fine_tune_resonator(self, c, setting, transmission_id):
        return self.send_command("fine_tune_resonator", {"setting": [setting],"transmission_id": transmission_id})    
    
    @setting(8,operation="y",transmission_id="i")
    def etalon_lock(self, c,  operation, transmission_id):
        return self.send_command( "etalon_lock", {"operation": operation, "transmission_id": transmission_id})
    
    @setting(9,transmission_id="i")
    def etalon_status(self, c, transmission_id):
        print("done")
        return self.send_command( "etalon_lock_status", {"transmission_id": transmission_id})
    
    @setting(10)
    def test(self, c):
        print("test")
    
    # def start_fast_scan(s, scan_type, scan_width, time, transmission_id):
    #     return send_command(s, "fast_scan_start", {"scan": scan_type, "width": [scan_width], "time": time,"transmission_id": transmission_id})
    def start_client(self,reg_vals):        
            
        response = self.start_link(self.laser_socket, "192.168.1.6",994)
        response_data = json.loads(response.decode('utf-8'))
        if response_data.get("message", {}).get("parameters", {}).get("status") == "ok":
            logging.debug("Init complete")
            # self.etalon_lock(s, 'on', 66)
            # etalon_response=self.etalon_status(self.laser_socket, 67)
            # etalon_response_data = json.loads(response.decode('utf-8'))
            # Check the etalon condition before fine-tuning
           
            # if etalon_response_data.get("message", {}).get("parameters", {}).get("condition") == "on": 
               
            # for i in range(47, 48):  # Outer loop from 45 to 46
            #     print("done1")
            #     for x in range(10):  # Inner loop from 0 to 9
            #         print("done2")
            #         fine_tune_percentage = i + 1
            #         time.sleep(3)
            #         print(x)
            #         # Assuming i.x means a decimal, you can represent it as i + x/10
            #         laser_msquared().tune_resonator(self.laser_socket,fine_tune_percentage + x/100, i+1)

__server__ = laserMsquared()        
            
if __name__ == '__main__':
    from labrad import util
    
    # reg_vals = ["192.168.0.222", 38939]
    # laserMsquared().on_get_config(reg_vals)
    # laserMsquared().poll_table_tuning(laserMsquared(),27)
    util.runServer(__server__)





