# -*- coding: utf-8 -*-
"""
Output server for the PI nanocube P-616.3C 3-axis piezo. 
Sending commands over usb

Created on Wed Nov  3 15:58:30 2021

@author: carter fox

### BEGIN NODE INFO
[info]
name = piezo_stage_616_3c_digital
version = 1.0
description =

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 
### END NODE INFO
"""


from labrad.server import LabradServer
from labrad.server import setting
from twisted.internet.defer import ensureDeferred
from pipython import GCSDevice
import nidaqmx
import logging
import numpy
import nidaqmx.stream_writers as stream_writers
import socket
from pathlib import Path
import time


class PiezoStageDigital(LabradServer):
    name = "piezo_stage_616_3c_digital"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.INFO, #INFO
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.task = None
        self.sub_init_server_xyz()

    def sub_init_server_xyz(self):
        """Sub-routine to be called by xyz server"""
        self.x_last_position = None
        self.x_current_direction = None
        self.x_last_turning_position = None
        self.y_last_position = None
        self.y_current_direction = None
        self.y_last_turning_position = None
        self.z_last_position = None
        self.z_current_direction = None
        self.z_last_turning_position = None
        config = ensureDeferred(self.get_config_xyz())
        config.addCallback(self.on_get_config_xyz)

    async def get_config_xyz(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "DeviceIDs"]) # change this in registry
        p.get("piezo_stage_616_3c_model")
        p.get("piezo_stage_616_3c_serial")
        # p.cd(["", "Config", "Wiring", "Piezo_stage_E727"])
        # p.get("piezo_stage_channel_x")
        # p.get("piezo_stage_channel_y")
        # p.cd(["", "Config", "Positioning"])
        # p.get("piezo_stage_voltage_range_factor")
        # p.get("daq_voltage_range_factor")
        # p.get("piezo_stage_scaling_offset")
        # p.get("piezo_stage_scaling_gain")
        # p.cd(["", "Config", "Wiring", "Daq"])
        # p.get("ao_piezo_stage_626_2cd_x")
        # p.get("ao_piezo_stage_626_2cd_y")
        # p.get("di_clock")
        p.cd(["", "Config", "Positioning"])
        p.get("xy_positional_accuracy") #using this for z accuracy too
        p.get("xy_timeout")
        # p.get("x_hysteresis_linearity")
        # p.get("y_hysteresis_linearity")
        result = await p.send()
        return result["get"]

    def on_get_config_xyz(self, config):
        # Load the generic device
        gcs_dll_path = str(Path.home())
        gcs_dll_path += "\\Documents\\GitHub\\kolkowitz-nv-experiment-v1.0"
        gcs_dll_path += "\\servers\\outputs\\GCSTranslator\\PI_GCS2_DLL_x64.dll" 
        
        self.piezo = GCSDevice(devname=config[0], gcsdll=gcs_dll_path)
        # Connect the specific device with the serial number
        self.piezo.ConnectUSB(config[1])        
        
        # Axis for device
        self.axis_0 = self.piezo.axes[0] 
        self.axis_1 = self.piezo.axes[1]
        self.axis_2 = self.piezo.axes[2]
        self.positioning_accuracy = config[2]
        self.timeout = config[3]
        # self.piezo_stage_channel_x = config[2]
        # self.piezo_stage_channel_y = config[3]
        
        # self.piezo_stage_voltage_range_factor = config[4]
        # self.daq_voltage_range_factor = config[5]
        
        # self.piezo_stage_scaling_offset = config[6]
        # self.piezo_stage_scaling_gain = config[7]
        # The command SPA allows us to rewrite volatile memory parameters.
        # The inputs are {item ID, Parameter ID, PArameter Value}
        
        # First, we need to make sure the input range on the piezo stage is accepting +/-5 volts

        # if self.piezo_stage_voltage_range_factor == 5.0:
        #     psvrf_value = 1
        # elif self.piezo_stage_voltage_range_factor  == 10.0:
        #     psvrf_value = 2
        # else:
        #     logging.debug("Piezo stage voltage range factor must be either 5.0 or 10.0")
        #     raise ValueError("Piezo stage voltage range factor must be either 5.0 or 10.0")
        # self.piezo.SPA(self.piezo_stage_channel_x, 0x02000100, psvrf_value)
        # self.piezo.SPA(self.piezo_stage_channel_y, 0x02000100, psvrf_value)
        # logging.debug("Piezo stage voltage range factor set to: {}".format(config[4]))
        
        
        # NExt, we need to set the right scaling for the input voltage to what the controller sends the piezo stage.
        # This is all defined in the E727 manual. The values below are for a stage
        # that travels between 0 and 500 um, and the input signal's range matching that of the controller's range (both 5 or 10 V)
        # self.piezo.SPA(self.piezo_stage_channel_x, 0x02000200, self.piezo_stage_scaling_offset) #offset
        # self.piezo.SPA(self.piezo_stage_channel_x, 0x02000300, self.piezo_stage_scaling_gain) #gain
        # self.piezo.SPA(self.piezo_stage_channel_y, 0x02000200, self.piezo_stage_scaling_offset) #offset
        # self.piezo.SPA(self.piezo_stage_channel_y, 0x02000300, self.piezo_stage_scaling_gain) #gain
        # logging.debug("Piezo stage scaling OFFSET set to: {}".format(self.piezo_stage_scaling_offset))
        # logging.debug("Piezo stage scaling GAIN set to: {}".format(config[7]))
        
        # Disconnect axis from analog channels
        self.piezo.SPA(self.axis_0, 0x06000500, 0)  # Disconnect axis 0
        self.piezo.SPA(self.axis_1, 0x06000500, 0)  # Disconnect axis 1
        self.piezo.SPA(self.axis_2, 0x06000500, 0)  # Disconnect axis 2
        # logging.debug("Piezo axis {} disconnected from analog signal".format(self.axis_0))
        # logging.debug("Piezo axis {} disconnected from analog signal".format(self.axis_1))
        
        # self.daq_ao_piezo_stage_x = config[8]
        # self.daq_ao_piezo_stage_y = config[9]
        # self.daq_di_clock = config[10]
        logging.info("Init Complete") #info
# %%
    # def load_stream_writer_xy(self, c, task_name, voltages, period):

    #     # Close the existing task if there is one
    #     if self.task is not None:
    #         self.close_task_internal()

    #     # Write the initial voltages and stream the rest
    #     num_voltages = voltages.shape[1]
    #     self.write_xy(c, voltages[0, 0], voltages[1, 0])
    #     stream_voltages = voltages[:, 1:num_voltages]
    #     stream_voltages = numpy.ascontiguousarray(stream_voltages)
    #     num_stream_voltages = num_voltages - 1
        
        
        

    #     # Configure the sample to advance on the rising edge of the PFI input.
    #     # The frequency specified is just the max expected rate in this case.
    #     # We'll stop once we've run all the samples.
    #     freq = float(1 / (period * (10 ** -9)))  # freq in seconds as a float
  
    #     task.timing.cfg_samp_clk_timing(
    #         freq, source=self.daq_di_clock, 
    #         samps_per_chan=num_stream_voltages
    #     )

    #     writer.write_many_sample(stream_voltages)

    #     # Close the task once we've written all the samples
    #     task.register_done_event(self.close_task_internal)

    #     task.start()

    # def close_task_internal(self, task_handle=None, status=None, callback_data=None):
    #     task = self.task
    #     if task is not None:
    #         task.close()
    #         self.task = None
    #     return 0

    @setting(32,  xPosition="v[]", yPosition="v[]", zPosition="v[]", returns="v[]",)
    def write_xyz(self, c, xPosition, yPosition, zPosition="v[]"):
        """Write the specified x and y and z voltages to the piezo stage"""
        if xPosition > 500 or yPosition > 500:
            logging.info("Piezo stage position must not exceed 500 um")
            raise ValueError("Piezo stage position must not exceed 500 um")
        if xPosition < 0 or yPosition < 0:
            logging.info("Piezo stage position must be above 0 um")
            raise ValueError("Piezo stage position must be above 0 um")
            
        # manually send voltage task to controller
        self.piezo.MOV(self.axis_0, xPosition)
        self.piezo.MOV(self.axis_1, yPosition) 
        self.piezo.MOV(self.axis_2, zPosition) 
        
        # Then check that we made it to the actual position, to within some threshold
        x_diff = 1000
        y_diff = 1000
        z_diff = 1000
        flag = 0
        time_start_check = time.time()
        while x_diff > self.positioning_accuracy or y_diff > self.positioning_accuracy or z_diff > self.positioning_accuracy:
            
            actual_x_pos, actual_y_pos, actual_z_pos = self.read_xyz(c)
            x_diff = abs(actual_x_pos - xPosition)
            y_diff = abs(actual_y_pos - yPosition)
            z_diff = abs(actual_z_pos - zPosition)
            time_check = time.time()
            if time_check - time_start_check > self.timeout:
                logging.info("Target position not reached!")
                flag = 1
                break 
            
        return flag
    
    @setting(35,  xPosition="v[]", returns="v[]",)
    def write_x(self, c, xPosition):
        """Write the specified x  voltage to the piezo stage"""
        if xPosition > 500 :
            logging.info("Piezo stage position must not exceed 500 um")
            raise ValueError("Piezo stage position must not exceed 500 um")
        if xPosition < 0:
            logging.info("Piezo stage position must be above 0 um")
            raise ValueError("Piezo stage position must be above 0 um")
            
        # manually send voltage task to controller
        self.piezo.MOV(self.axis_0, xPosition)
        
        # Then check that we made it to the actual position, to within some threshold
        x_diff = 1000
        flag = 0
        time_start_check = time.time()
        while x_diff > self.positioning_accuracy :
            
            actual_x_pos, actual_y_pos, actual_z_pos = self.read_xyz(c)
            x_diff = abs(actual_x_pos - xPosition)
            time_check = time.time()
            if time_check - time_start_check > self.timeout:
                logging.info("Target position not reached!")
                flag = 1
                break 
            
        return flag
    
    @setting(36,   yPosition="v[]", returns="v[]",)
    def write_y(self, c, yPosition):
        """Write the specified  y voltage to the piezo stage"""
        if yPosition > 500:
            logging.info("Piezo stage position must not exceed 500 um")
            raise ValueError("Piezo stage position must not exceed 500 um")
        if yPosition < 0:
            logging.info("Piezo stage position must be above 0 um")
            raise ValueError("Piezo stage position must be above 0 um")
            
        # manually send voltage task to controller
        self.piezo.MOV(self.axis_1, yPosition) 
        
        # Then check that we made it to the actual position, to within some threshold
        y_diff = 1000
        flag = 0
        time_start_check = time.time()
        while y_diff > self.positioning_accuracy:
            
            actual_x_pos, actual_y_pos, actual_z_pos = self.read_xyz(c)
            y_diff = abs(actual_y_pos - yPosition)
            time_check = time.time()
            if time_check - time_start_check > self.timeout:
                logging.info("Target position not reached!")
                flag = 1
                break 
            
        return flag

    @setting(86,   zPosition="v[]", returns="v[]",)
    def write_z(self, c, zPosition):
        """Write the specified  z voltage to the piezo stage"""
        if zPosition > 500:
            logging.info("Piezo stage position must not exceed 500 um")
            raise ValueError("Piezo stage position must not exceed 500 um")
        if zPosition < 0:
            logging.info("Piezo stage position must be above 0 um")
            raise ValueError("Piezo stage position must be above 0 um")
            
        # manually send voltage task to controller
        self.piezo.MOV(self.axis_2, zPosition) 
        
        # Then check that we made it to the actual position, to within some threshold
        z_diff = 1000
        flag = 0
        time_start_check = time.time()
        while z_diff > self.positioning_accuracy:
            
            actual_x_pos, actual_y_pos, actual_z_pos = self.read_xyz(c)
            z_diff = abs(actual_z_pos - zPosition)
            time_check = time.time()
            if time_check - time_start_check > self.timeout:
                logging.info("Target position not reached!")
                flag = 1
                break 
            
        return flag

    # @setting(31, returns="*v[]")
    # def read_xy(self, c):
    #     """Return the current voltages on the piezo's DAQ channels"""
        
    #     ordered_dict = self.piezo.qPOS(self.axis_0)
    #     xPosition = ordered_dict["{}".format(self.axis_0)]
    #     ordered_dict = self.piezo.qPOS(self.axis_1)
    #     yPosition = ordered_dict["{}".format(self.axis_1)]
    #     return xPosition, yPosition
    
    @setting(71, returns="*v[]")
    def read_xyz(self, c):
        """Return the current voltages on the piezo's DAQ channels"""
        
        ordered_dict = self.piezo.qPOS(self.axis_0)
        xPosition = ordered_dict["{}".format(self.axis_0)]
        ordered_dict = self.piezo.qPOS(self.axis_1)
        yPosition = ordered_dict["{}".format(self.axis_1)]
        ordered_dict = self.piezo.qPOS(self.axis_2)
        zPosition = ordered_dict["{}".format(self.axis_2)]
        return xPosition, yPosition, zPosition

    @setting(33, returns="*v[]")
    def check_on_target(self, c):
        """Checks controller to see if piezo is set to current target position
        Will output 1 for True and 0 for False"""
        
        ordered_dict = self.piezo.qONT(self.axis_0)
        on_target_x = ordered_dict["{}".format(self.axis_0)]
        ordered_dict = self.piezo.qONT(self.axis_1)
        on_target_y = ordered_dict["{}".format(self.axis_1)]
        ordered_dict = self.piezo.qONT(self.axis_2)
        on_target_z = ordered_dict["{}".format(self.axis_2)]
        return on_target_x, on_target_y, on_target_z
    
    @setting(34, returns="*v[]")
    def check_servo_mode(self, c):
        """Checks servo mode"""
        
        ordered_dict = self.piezo.qSVO(self.axis_0)
        servo_mode_x = ordered_dict["{}".format(self.axis_0)]
        ordered_dict = self.piezo.qSVO(self.axis_1)
        servo_mode_y = ordered_dict["{}".format(self.axis_1)]
        ordered_dict = self.piezo.qSVO(self.axis_2)
        servo_mode_z = ordered_dict["{}".format(self.axis_2)]
        
        logging.info(servo_mode_x, servo_mode_y, servo_mode_z)
        return servo_mode_x, servo_mode_y, servo_mode_z

    @setting(
        2,
        x_center="v[]",
        y_center="v[]",
        x_range="v[]",
        y_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]*v[]",
    )
    def load_sweep_scan_xy(
        self, c, x_center, y_center, x_range, y_range, num_steps, period
    ):
        """Load a scan that will wind through the grid defined by the passed
        parameters. Samples are advanced by the clock. Currently x_range
        must equal y_range.

        Normal scan performed, starts in bottom right corner, and starts
        heading left

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            x_range: float
                Full scan range in x
            y_range: float
                Full scan range in y
            num_steps: int
                Number of steps the break the ranges into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
            list(float)
                The y voltages that make up the scan
        """

        ######### Assumes x_range == y_range #########

        if x_range != y_range:
            raise ValueError("x_range must equal y_range for now")

        x_num_steps = num_steps
        y_num_steps = num_steps

        # Force the scan to have square pixels by only applying num_steps
        # to the shorter axis
        half_x_range = x_range / 2
        half_y_range = y_range / 2

        x_low = x_center - half_x_range
        x_high = x_center + half_x_range
        y_low = y_center - half_y_range
        y_high = y_center + half_y_range

        # Apply scale and offset to get the voltages we'll apply to the stage
        # Note that the polar/azimuthal angles, not the actual x/y positions
        # are linear in these voltages. For a small range, however, we don't
        # really care.
        x_voltages_1d = numpy.linspace(x_low, x_high, num_steps)
        y_voltages_1d = numpy.linspace(y_low, y_high, num_steps)

        ######### Works for any x_range, y_range #########

        # Winding cartesian product
        # The x values are repeated and the y values are mirrored and tiled
        # The comments below shows what happens for [1, 2, 3], [4, 5, 6]

        # [1, 2, 3] => [1, 2, 3, 3, 2, 1]
        x_inter = numpy.concatenate((x_voltages_1d, numpy.flipud(x_voltages_1d)))
        # [1, 2, 3, 3, 2, 1] => [1, 2, 3, 3, 2, 1, 1, 2, 3]
        if y_num_steps % 2 == 0:  # Even x size
            x_voltages = numpy.tile(x_inter, int(y_num_steps / 2))
        else:  # Odd x size
            x_voltages = numpy.tile(x_inter, int(numpy.floor(y_num_steps / 2)))
            x_voltages = numpy.concatenate((x_voltages, x_voltages_1d))

        # [4, 5, 6] => [4, 4, 4, 5, 5, 5, 6, 6, 6]
        y_voltages = numpy.repeat(y_voltages_1d, x_num_steps)

        voltages = numpy.vstack((x_voltages, y_voltages))

        # logging.debug(voltages)
        # self.load_stream_writer_xy(c, "Piezo_stage-load_sweep_scan_xy", voltages, period)

        return x_voltages_1d, y_voltages_1d

    @setting(
        92,
        x_center="v[]",
        y_center="v[]",
        z_center="v[]",
        x_range="v[]",
        z_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]*v[]",
    )
    def load_sweep_scan_xz(
        self, c, x_center, y_center, z_center, x_range, z_range, num_steps, period
    ):
        """Load a scan that will wind through the grid defined by the passed
        parameters. Samples are advanced by the clock. Currently x_range
        must equal z_range.

        Normal scan performed, starts in bottom right corner, and starts
        heading left

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            z_center: float
                Center z voltage of the scan
            x_range: float
                Full scan range in x
            z_range: float
                Full scan range in z
            num_steps: int
                Number of steps the break the ranges into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
            list(float)
                The z voltages that make up the scan
        """

        ######### Assumes x_range == y_range #########

        if x_range != z_range:
            raise ValueError("x_range must equal z_range for now")

        x_num_steps = num_steps
        z_num_steps = num_steps

        # Force the scan to have square pixels by only applying num_steps
        # to the shorter axis
        half_x_range = x_range / 2
        half_z_range = z_range / 2

        x_low = x_center - half_x_range
        x_high = x_center + half_x_range
        z_low = z_center - half_z_range
        z_high = z_center + half_z_range

        # Apply scale and offset to get the voltages we'll apply to the stage
        # Note that the polar/azimuthal angles, not the actual x/z positions
        # are linear in these voltages. For a small range, however, we don't
        # really care.
        x_voltages_1d = numpy.linspace(x_low, x_high, num_steps)
        z_voltages_1d = numpy.linspace(z_low, z_high, num_steps)

        ######### Works for any x_range, z_range #########

        # Winding cartesian product
        # The x values are repeated and the y values are mirrored and tiled
        # The comments below shows what happens for [1, 2, 3], [4, 5, 6]

        # [1, 2, 3] => [1, 2, 3, 3, 2, 1]
        x_inter = numpy.concatenate((x_voltages_1d, numpy.flipud(x_voltages_1d)))
        # [1, 2, 3, 3, 2, 1] => [1, 2, 3, 3, 2, 1, 1, 2, 3]
        if z_num_steps % 2 == 0:  # Even x size
            x_voltages = numpy.tile(x_inter, int(z_num_steps / 2))
        else:  # Odd x size
            x_voltages = numpy.tile(x_inter, int(numpy.floor(z_num_steps / 2)))
            x_voltages = numpy.concatenate((x_voltages, x_voltages_1d))

        # [4, 5, 6] => [4, 4, 4, 5, 5, 5, 6, 6, 6]
        z_voltages = numpy.repeat(z_voltages_1d, x_num_steps)
        y_voltages = numpy.empty(len(z_voltages))
        y_voltages.fill(y_center)

        voltages = numpy.vstack((x_voltages, y_voltages, z_voltages))

        # logging.debug(voltages)
        # self.load_stream_writer_xz(c, "Piezo_stage-load_sweep_scan_xy", voltages, period)

        return x_voltages_1d, z_voltages_1d

    

    @setting(
        63,
        x_center="v[]",
        y_center="v[]",
        z_center="v[]",
        scan_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]",
    )
    def load_scan_x(self, c, x_center, y_center, z_center, scan_range, num_steps, period):
        """Load a scan that will step through scan_range in x keeping y and z
        constant at its center.

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            z_center: float
                Center z voltage of the scan
            scan_range: float
                Full scan range in x/y/z
            num_steps: int
                Number of steps the break the x/y/z range into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
        """

        half_scan_range = scan_range / 2

        x_low = x_center - half_scan_range
        x_high = x_center + half_scan_range

        z_voltages = numpy.full(num_steps, z_center)
        y_voltages = numpy.full(num_steps, y_center)
        x_voltages = numpy.linspace(x_low, x_high, num_steps)

        voltages = numpy.vstack((x_voltages, y_voltages, z_voltages))

        # self.load_stream_writer_xy(c, "Piezo_stage-load_scan_y", voltages, period)

        return x_voltages

    @setting(
        64,
        x_center="v[]",
        y_center="v[]",
        z_center="v[]",
        scan_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]",
    )
    def load_scan_y(self, c, x_center, y_center, z_center, scan_range, num_steps, period):
        """Load a scan that will step through scan_range in y keeping x and z
        constant at its center.

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            z_center: float
                Center z voltage of the scan
            scan_range: float
                Full scan range in x/y/z
            num_steps: int
                Number of steps the break the x/y/z range into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The y voltages that make up the scan
        """

        half_scan_range = scan_range / 2

        y_low = y_center - half_scan_range
        y_high = y_center + half_scan_range

        x_voltages = numpy.full(num_steps, x_center)
        z_voltages = numpy.full(num_steps, z_center)
        y_voltages = numpy.linspace(y_low, y_high, num_steps)

        voltages = numpy.vstack((x_voltages, y_voltages, z_voltages))

        # self.load_stream_writer_xy(c, "Piezo_stage-load_scan_y", voltages, period)

        return y_voltages
    
    @setting(
        65,
        x_center="v[]",
        y_center="v[]",
        z_center="v[]",
        scan_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]",
    )
    def load_scan_z(self, c, x_center, y_center, z_center, scan_range, num_steps, period):
        """Load a scan that will step through scan_range in z keeping x and y
        constant at its center.

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            z_center: float
                Center z voltage of the scan
            scan_range: float
                Full scan range in x/y/z
            num_steps: int
                Number of steps the break the x/y/z range into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The z voltages that make up the scan
        """

        half_scan_range = scan_range / 2

        z_low = z_center - half_scan_range
        z_high = z_center + half_scan_range

        x_voltages = numpy.full(num_steps, x_center)
        y_voltages = numpy.full(num_steps, y_center)
        z_voltages = numpy.linspace(z_low, z_high, num_steps)

        voltages = numpy.vstack((x_voltages, y_voltages, z_voltages))

        # self.load_stream_writer_xy(c, "Piezo_stage-load_scan_y", voltages, period)

        return z_voltages

    # @setting(6, x_points="*v[]", y_points="*v[]", period="i")
    # def load_arb_scan_xy(self, c, x_points, y_points, period):
    #     """Load a scan that goes between points. E.i., starts at [1,1] and
    #     then on a clock pulse, moves to [2,1]. Can work for arbitrarily large
    #     number of points 
    #     (previously load_two_point_xy_scan)

    #     Params
    #         x_points: list(float)
    #             X values correspnding to positions in x
    #             y_points: list(float)
    #             Y values correspnding to positions in y
    #         period: int
    #             Expected period between clock signals in ns

    #     """

    #     voltages = numpy.vstack((x_points, y_points))

    #     self.load_stream_writer_xy(c, "Piezo_stage-load_arb_scan_xy", voltages, period)

    #     return



__server__ = PiezoStageDigital()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
