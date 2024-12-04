# -*- coding: utf-8 -*-
"""
Output server for the Thorlabs GVS212 galvanometer. Controlled by an NI DAQ.

Created on September 6th, 2024

@author: wwu

### BEGIN NODE INFO
[info]
name = pos_xyz_Newport_25XA
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
from twisted.internet.defer import ensureDeferred
import numpy as np
import logging
import socket
import json
import os
import time


class PosXyzNewport25XA(LabradServer):
    name = "pos_xyz_Newport_25XA"
    pc_name = socket.gethostname()

    def initServer(self):

        filename = (
            "D:/Choy_Lab/"
            "sivdata/labrad_logging/{}.log"
        )
        filename = filename.format(self.name)
        # os.makedirs(filename, exist_ok=True)
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

        self.stage_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.stage_socket.connect((reg_vals[0], reg_vals[1]))
            print(reg_vals[0], reg_vals[1])
            response = self.send_command("VE?")
            response_str = response.decode('utf-8').strip()
            logging.info(response_str)
            # logging.info(f"{response_str}")

        except Exception as e:
            # Log any exceptions that occur during connection
            print(e)
            logging.info(e)
            del self.stage_socket

    def send_command(self, command):
        try:
            self.stage_socket.settimeout(1.0)  # Set a 5-second timeout
            self.stage_socket.sendall(f"{command}\r".encode())
            response = self.stage_socket.recv(1024)  # Adjust buffer size if needed
            print(f"send_command: Received response: {repr(response)}")
            return response
        except socket.timeout:
            print(f"send_command: Timeout waiting for response to {command}")
            return None
        except Exception as e:
            print(f"send_command: Error: {e}")
            raise

    def stopServer(self):
        self.close_task_internal()

    def close_task_internal(self, task_handle=None, status=None, callback_data=None):
        task = self.task
        if task is not None:
            task.close()
            self.task = None
        return 0

    @setting(0, axis="i", returns = "v")  
    def get_axis_position(self, c, axis):
        """Send command to get the position of the specified axis.

        Args:
            axis (int): Axis number (1 for X-axis, 2 for Y-axis, 3 for Z-axis).

        Returns:
            float: Current position of the axis.
        """
        # command = f"{axis}TP\r"  
        # response = self.send_command(command)
        # response_str = response.decode('utf-8').strip()
        # response_parts = response_str.split(',')

        command = f"{axis}TP\r"  # Send command to get position
        response = self.send_command(command)
        response_str = response.decode('utf-8').strip()

        try:
                position = float(response_str)
                return position
        except ValueError as e:
            raise ValueError(f"Invalid response from controller: {response_str}") from e

    @setting(1, axis="i", position="v")
    def write_absolute(self, c, axis, position):
        """Move the specified axis to an absolute position."""
        command = f"{axis}PA{position}"  # 'PA' (Position Absolute) command
        self.send_command(command)

    @setting(2, axis="i", position="v")
    def write_relative(self, c, axis, position):
        """Move the specified axis to an absolute position."""
        command = f"{axis}PR{position}"
        self.send_command(command)
    
    @setting(3, axis="i")
    def stop_motion(self, c, axis):
        """Stop the motion of the specified axis."""
        command = f"{axis}ST"
        self.send_command(command)
    
    @setting(4, x_start="v", x_stop="v", y_start="v", y_stop="v", num_steps="i", period="i")
    def raster_scan(self, c, x_start, x_stop, y_start, y_stop, num_steps, period):
        """Perform a raster scan (X: 2, Y: 3)."""
        x_positions = np.linspace(x_start, x_stop, num_steps)
        y_positions = np.linspace(y_start, y_stop, num_steps)
        for y in y_positions:
            for x in x_positions:
                self.write_absolute(c, 2, x)  # Move X axis (Axis 2)
                self.write_absolute(c, 3, y)  # Move Y axis (Axis 3)
                time.sleep(period / 1000)  # Dwell time at each point

    @setting(5, x_center="v", y_center="v", xy_range="v", num_steps="i", period="i")
    def cross_scan(self, c, x_center, y_center, xy_range, num_steps, period):
        """Perform a cross scan (X: 2, Y: 3)."""
        x_voltages = np.linspace(x_center - xy_range / 2, x_center + xy_range / 2, num_steps)
        y_voltages = np.linspace(y_center - xy_range / 2, y_center + xy_range / 2, num_steps)

        # Scan X (Axis 2) with Y (Axis 3) fixed
        for x in x_voltages:
            self.write_absolute(c, 2, x)
            self.write_absolute(c, 3, y_center)
            time.sleep(period / 1000)

        # Scan Y (Axis 3) with X (Axis 2) fixed
        for y in y_voltages:
            self.write_absolute(c, 2, x_center)
            self.write_absolute(c, 3, y)
            time.sleep(period / 1000)           
        @setting(8)
        def reset(self):
            self.close_task_internal()
    
    @setting(6, radius="v", num_steps="i", period="i")
    def circular_scan(self, c, radius, num_steps, period):
        """Perform a circular scan around the origin (X: 2, Y: 3)."""
        angles = np.linspace(0, 2 * np.pi, num_steps)
        x_positions = radius * np.cos(angles)
        y_positions = radius * np.sin(angles)

        for x, y in zip(x_positions, y_positions):
            self.write_absolute(c, 2, x)  # X axis (Axis 2)
            self.write_absolute(c, 3, y)  # Y axis (Axis 3)
            time.sleep(period / 1000)

    @setting(7, returns="v[]")
    def read_xy(self, c):
        """Read the positions of both X (Axis 2) and Y (Axis 3) axes."""
        x_position = self.get_axis_position(c, 2)
        y_position = self.get_axis_position(c, 3)
        return x_position, y_position
    
    @setting(8, returns="v")
    def read_z(self, c):
        """Read the position of the Z (Axis 1) axis."""
        z_position = self.get_axis_position(c, 1)
        return z_position
    
    @setting(9, returns="*v")
    def read_xyz(self, c):
        """Read the positions of both X (Axis 2) and Y (Axis 3) axes."""
        x_position = self.get_axis_position(c, 2)
        y_position = self.get_axis_position(c, 3)
        z_position = self.get_axis_position(c, 1)
        return x_position, y_position, z_position
    
    @setting(10, x_position="v", y_position="v")
    def write_xy(self, c, x_position, y_position):
        """
        Move both the X (Axis 2) and Y (Axis 3) axes to specified absolute positions.

        Args:
            x_position (float): The position for the X-axis.
            y_position (float): The position for the Y-axis.
        """
        # Move X and Y axes to absolute positions
        print(f"write_xy called with x: {x_position}, y: {y_position}")
        self.write_absolute(c, 2, x_position)  # Absolute move for X-axis (Axis 2)
        self.write_absolute(c, 3, y_position)  # Absolute move for Y-axis (Axis 3)

    @setting(11, z_position="v")
    def write_z(self, c, z_position):
        """
        Move the Z (Axis 1) axis to the specified absolute position.

        Args:
            position (float): The desired position for the Z-axis.
        """
        # Move Z axis to absolute position
        print(f"write_z called with z: {z_position}")
        self.write_absolute(c, 1, z_position)  # Absolute move for Z-axis (Axis 1)



__server__ = PosXyzNewport25XA()

if __name__ == "__main__":
    from labrad import util
    # Initialize your PosXyzNewport25XA class
    # pos_controller = PosXyzNewport25XA()
    # reg_vals = ["192.168.1.90", 5001]
    # pos_controller.on_get_config(reg_vals)
    # # pos_controller.send_command("1TP")
    # pos_controller.send_command("1PA1.0")

    util.runServer(__server__)
