# -*- coding: utf-8 -*-
"""
Output server for the PI P-616.3C 3-axis nanocube piezo. 

Created on Wed Nov  3 15:58:30 2021

@author: carter fox

### BEGIN NODE INFO
[info]
name = pos_xyz_PI_616_3c
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


class PosXyzPi6163c(LabradServer):
    name = "pos_xyz_PI_616_3c"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.DEBUG,
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
        p.cd(["", "Config", "Wiring", "Piezo_stage_E616"])
        p.get("piezo_stage_channel_x")
        p.get("piezo_stage_channel_y")
        p.get("piezo_stage_channel_z")
        p.cd(["", "Config", "Positioning"])
        p.get("piezo_stage_voltage_range_factor")
        p.get("daq_voltage_range_factor")
        p.get("piezo_stage_scaling_offset")
        p.get("piezo_stage_scaling_gain")
        p.cd(["", "Config", "Wiring", "Daq"])
        p.get("ao_piezo_stage_616_3c_x")
        p.get("ao_piezo_stage_616_3c_y")
        p.get("ao_piezo_stage_616_3c_z")
        p.get("di_clock")
        # p.cd(["", "Config", "Positioning"])
        # p.get("x_hysteresis_linearity")
        # p.get("y_hysteresis_linearity")
        result = await p.send()
        return result["get"]

    def on_get_config_xyz(self, config):
        # Load the generic device
        gcs_dll_path = str(Path.home())
        gcs_dll_path += "\\Documents\\GitHub\\kolkowitz-nv-experiment-v1.0"
        gcs_dll_path += "\\servers\\outputs\\GCSTranslator\\PI_GCS2_DLL_x64.dll" ###I think this is still fine. 
        
        self.piezo = GCSDevice(devname=config[0], gcsdll=gcs_dll_path)
        # Connect the specific device with the serial number
        self.piezo.ConnectUSB(config[1])        
        
        # Just one axis for this device
        self.axis_0 = self.piezo.axes[0] 
        self.axis_1 = self.piezo.axes[1]
        
        self.piezo_stage_channel_x = config[2]
        self.piezo_stage_channel_y = config[3]
        self.piezo_stage_channel_y = config[4]
        
        self.piezo_stage_voltage_range_factor = config[5]
        self.daq_voltage_range_factor = config[6]
        
        self.piezo_stage_scaling_offset = config[7]
        self.piezo_stage_scaling_gain = config[8]
        # The command SPA allows us to rewrite volatile memory parameters.
        # The inputs are {item ID, Parameter ID, PArameter Value}
        
        # First, we need to make sure the input range on the piezo stage is accepting +/-5 volts

        if self.piezo_stage_voltage_range_factor == 5.0:
            psvrf_value = 1
        elif self.piezo_stage_voltage_range_factor  == 10.0:
            psvrf_value = 2
        else:
            logging.debug("Piezo stage voltage range factor must be either 5.0 or 10.0")
            raise ValueError("Piezo stage voltage range factor must be either 5.0 or 10.0")
        self.piezo.SPA(self.piezo_stage_channel_x, 0x02000100, psvrf_value)
        self.piezo.SPA(self.piezo_stage_channel_y, 0x02000100, psvrf_value)
        self.piezo.SPA(self.piezo_stage_channel_z, 0x02000100, psvrf_value)
        logging.debug("Piezo stage voltage range factor set to: {}".format(config[5]))
        
        
        # NExt, we need to set the right scaling for the input voltage to what the controller sends the piezo stage.
        # This is all defined in the E727 manual. The values below are for a stage
        # that travels between 0 and 500 um, and the input signal's range matching that of the controller's range (both 5 or 10 V)
        self.piezo.SPA(self.piezo_stage_channel_x, 0x02000200, self.piezo_stage_scaling_offset) #offset
        self.piezo.SPA(self.piezo_stage_channel_x, 0x02000300, self.piezo_stage_scaling_gain) #gain
        self.piezo.SPA(self.piezo_stage_channel_y, 0x02000200, self.piezo_stage_scaling_offset) #offset
        self.piezo.SPA(self.piezo_stage_channel_y, 0x02000300, self.piezo_stage_scaling_gain) #gain
        self.piezo.SPA(self.piezo_stage_channel_z, 0x02000200, self.piezo_stage_scaling_offset) #offset
        self.piezo.SPA(self.piezo_stage_channel_z, 0x02000300, self.piezo_stage_scaling_gain) #gain
        logging.debug("Piezo stage scaling OFFSET set to: {}".format(self.piezo_stage_scaling_offset))
        logging.debug("Piezo stage scaling GAIN set to: {}".format(config[8]))
        
        # Finally, internally connect the controller's X/Y axis to the incomming signal on channels 4/5
        self.piezo.SPA(self.axis_0, 0x06000500, self.piezo_stage_channel_x)  # Axis 0 will be controlled by channel 5
        self.piezo.SPA(self.axis_1, 0x06000500, self.piezo_stage_channel_y)  # Axis 0 will be controlled by channel 6
        self.piezo.SPA(self.axis_2, 0x06000500, self.piezo_stage_channel_z)  # Axis 0 will be controlled by channel 7
        logging.debug("Piezo axis {} connected to channel {}".format(self.axis_0, self.piezo_stage_channel_x))
        logging.debug("Piezo axis {} connected to channel {}".format(self.axis_1, self.piezo_stage_channel_y))
        logging.debug("Piezo axis {} connected to channel {}".format(self.axis_2, self.piezo_stage_channel_z))
        
        self.daq_ao_piezo_stage_x = config[9]
        self.daq_ao_piezo_stage_y = config[10]
        self.daq_ao_piezo_stage_z = config[11]
        self.daq_di_clock = config[12]
        logging.debug("Init Complete")
# %%
    def load_stream_writer_xy(self, c, task_name, voltages, period):

        # Close the existing task if there is one
        if self.task is not None:
            self.close_task_internal()

        # Write the initial voltages and stream the rest
        num_voltages = voltages.shape[1]
        self.write_xy(c, voltages[0, 0], voltages[1, 0])
        stream_voltages = voltages[:, 1:num_voltages]
        stream_voltages = numpy.ascontiguousarray(stream_voltages)
        num_stream_voltages = num_voltages - 1
        # Create a new task
        task = nidaqmx.Task(task_name)
        self.task = task
        
        

        # Set up the output channels
        # task.ao_channels.add_ao_voltage_chan(
        #     self.daq_ao_piezo_stage_x, min_val=-self.daq_voltage_range_factor, 
        #                                 max_val=self.daq_voltage_range_factor
        # )
        # task.ao_channels.add_ao_voltage_chan(
        #     self.daq_ao_piezo_stage_y, min_val=-self.daq_voltage_range_factor, 
        #                                 max_val=self.daq_voltage_range_factor
        # )
        
        channel_0 =task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_x, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        channel_1 =task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_y, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        
        # Set the daq reference value to either 5 or 10 V
        channel_0.ao_dac_ref_val = self.daq_voltage_range_factor
        channel_1.ao_dac_ref_val = self.daq_voltage_range_factor

        # Set up the output stream
        output_stream = nidaqmx.task.OutStream(task)
        writer = stream_writers.AnalogMultiChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        # We'll stop once we've run all the samples.
        freq = float(1 / (period * (10 ** -9)))  # freq in seconds as a float
  
        task.timing.cfg_samp_clk_timing(
            freq, source=self.daq_di_clock, 
            samps_per_chan=num_stream_voltages
        )

        writer.write_many_sample(stream_voltages)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)

        task.start()
        
    def load_stream_writer_xyz(self, c, task_name, voltages, period):

        # Close the existing task if there is one
        if self.task is not None:
            self.close_task_internal()

        # Write the initial voltages and stream the rest
        num_voltages = voltages.shape[1]
        self.write_xyz(c, voltages[0, 0], voltages[1, 0], voltages[2, 0])
        stream_voltages = voltages[:, 1:num_voltages]
        stream_voltages = numpy.ascontiguousarray(stream_voltages)
        num_stream_voltages = num_voltages - 1
        # Create a new task
        task = nidaqmx.Task(task_name)
        self.task = task
 
        
        channel_0 =task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_x, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        channel_1 =task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_y, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        channel_2 =task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_z, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        
        # Set the daq reference value to either 5 or 10 V
        channel_0.ao_dac_ref_val = self.daq_voltage_range_factor
        channel_1.ao_dac_ref_val = self.daq_voltage_range_factor
        channel_2.ao_dac_ref_val = self.daq_voltage_range_factor

        # Set up the output stream
        output_stream = nidaqmx.task.OutStream(task)
        writer = stream_writers.AnalogMultiChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        # We'll stop once we've run all the samples.
        freq = float(1 / (period * (10 ** -9)))  # freq in seconds as a float
  
        task.timing.cfg_samp_clk_timing(
            freq, source=self.daq_di_clock, 
            samps_per_chan=num_stream_voltages
        )

        writer.write_many_sample(stream_voltages)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)

        task.start()

    def close_task_internal(self, task_handle=None, status=None, callback_data=None):
        task = self.task
        if task is not None:
            task.close()
            self.task = None
        return 0

    @setting(32,  xVoltage="v[]", yVoltage="v[]") ###???? Do i need to change the decorators ????
    def write_xy(self, c, xVoltage, yVoltage):
        """Write the specified x and y voltages to the piezo stage"""

        # Close the stream task if it exists
        # This can happen if we quit out early
        if self.task is not None:
            self.close_task_internal()


        with nidaqmx.Task() as task:
            # Set up the output channels
            channel_0 = task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_piezo_stage_x, min_val=-self.daq_voltage_range_factor,
                                        max_val=self.daq_voltage_range_factor
            )
        
            channel_1 = task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_piezo_stage_y, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
            )
            
            channel_0.ao_dac_ref_val = self.daq_voltage_range_factor
            channel_1.ao_dac_ref_val = self.daq_voltage_range_factor
            
            task.write([xVoltage, yVoltage])
    
    @setting(42,  xVoltage="v[]", yVoltage="v[]", zVoltage="v[]")
    def write_xyz(self, c, xVoltage, yVoltage, zVoltage):
        """Write the specified x and y and z voltages to the piezo stage"""

        # Close the stream task if it exists
        # This can happen if we quit out early
        if self.task is not None:
            self.close_task_internal()


        with nidaqmx.Task() as task:
            # Set up the output channels
            channel_0 = task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_piezo_stage_x, min_val=-self.daq_voltage_range_factor,
                                        max_val=self.daq_voltage_range_factor
            )
        
            channel_1 = task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_piezo_stage_y, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
            )
            channel_2 = task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_piezo_stage_z, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
            )
            
            channel_0.ao_dac_ref_val = self.daq_voltage_range_factor
            channel_1.ao_dac_ref_val = self.daq_voltage_range_factor
            channel_2.ao_dac_ref_val = self.daq_voltage_range_factor
            
            task.write([xVoltage, yVoltage, zVoltage])


    @setting(31, returns="*v[]")
    def read_xy(self, c):
        """Return the current voltages on the piezo's DAQ channels"""
        with nidaqmx.Task() as task:
            # Set up the internal channels - to do: actual parsing...
            if self.daq_ao_piezo_stage_x == "dev1/AO0":
                chan_name = "dev1/_ao0_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, 
                                     min_val=-self.daq_voltage_range_factor, 
                                     max_val=self.daq_voltage_range_factor)
            if self.daq_ao_piezo_stage_y == "dev1/AO1":
                chan_name = "dev1/_ao1_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, 
                                     min_val=-self.daq_voltage_range_factor, 
                                     max_val=self.daq_voltage_range_factor)
            voltages = task.read()

        return voltages[0], voltages[1]


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
    
    @setting(51, returns="*v[]")
    def read_xyz(self, c):
        """Return the current voltages on the piezo's DAQ channels"""
        with nidaqmx.Task() as task:
            # Set up the internal channels - to do: actual parsing...
            if self.daq_ao_piezo_stage_x == "dev1/AO0":
                chan_name = "dev1/_ao0_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, 
                                     min_val=-self.daq_voltage_range_factor, 
                                     max_val=self.daq_voltage_range_factor)
            if self.daq_ao_piezo_stage_y == "dev1/AO1":
                chan_name = "dev1/_ao1_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, 
                                     min_val=-self.daq_voltage_range_factor, 
                                     max_val=self.daq_voltage_range_factor)
            if self.daq_ao_piezo_stage_z == "dev1/AO2":
                chan_name = "dev1/_ao2_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, 
                                     min_val=-self.daq_voltage_range_factor, 
                                     max_val=self.daq_voltage_range_factor)
            voltages = task.read()

        return voltages[0], voltages[1], voltages[2]


    @setting(
        52,
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
        self.load_stream_writer_xy(c, "Piezo_stage-load_sweep_scan_xy", voltages, period)

        return x_voltages_1d, y_voltages_1d
    
    @setting(
        62,
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
        parameters. Samples are advanced by the clock. 

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
        # The x values are repeated and the z values are mirrored and tiled
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
        self.load_stream_writer_xyz(c, "Piezo_stage-load_sweep_scan_xz", voltages, period)

        return x_voltages_1d, z_voltages_1d
    
    
    @setting(
        3,
        x_center="v[]",
        y_center="v[]",
        xy_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]*v[]",
    )
    def load_cross_scan_xy(self, c, x_center, y_center, xy_range, num_steps, period):
        """Load a scan that will first step through xy_range in x keeping y
        constant at its center, then step through xy_range in y keeping x
        constant at its center.

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            xy_range: float
                Full scan range in x/y
            num_steps: int
                Number of steps the break the x/y range into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
            list(float)
                The y voltages that make up the scan
        """

        half_xy_range = xy_range / 2

        x_low = x_center - half_xy_range
        x_high = x_center + half_xy_range
        y_low = y_center - half_xy_range
        y_high = y_center + half_xy_range

        x_voltages_1d = numpy.linspace(x_low, x_high, num_steps)
        y_voltages_1d = numpy.linspace(y_low, y_high, num_steps)

        x_voltages = numpy.concatenate([x_voltages_1d, numpy.full(num_steps, x_center)])
        y_voltages = numpy.concatenate([numpy.full(num_steps, y_center), y_voltages_1d])

        voltages = numpy.vstack((x_voltages, y_voltages))

        self.load_stream_writer_xy(c, "Piezo_stage-load_cross_scan_xy", voltages, period)

        return x_voltages_1d, y_voltages_1d

    @setting(
        7,
        radius="v[]",
        num_steps="i",
        period="i",
        returns="*v[]*v[]",
    )
    def load_circle_scan_xy(self, c, radius, num_steps, period):
        """Load a circle scan centered about 0,0. Useful for testing cat's eye
        stationary point. For this reason, the scan runs continuously, not
        just until it makes it through all the samples once. 

        Params
            radius: float
                Radius of the circle in V
            num_steps: int
                Number of steps the break the x/y range into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
            list(float)
                The y voltages that make up the scan
        """
        
        angles = numpy.linspace(0, 2*numpy.pi, num_steps)

        x_voltages = radius * numpy.sin(angles)

        y_voltages = radius * numpy.cos(angles)
        # y_voltages = numpy.zeros(len(angles))

        voltages = numpy.vstack((x_voltages, y_voltages))

        self.load_stream_writer_xy(c, "Piezo_stage-load_circle_scan_xy", voltages, 
                                   period, True)

        return x_voltages, y_voltages

    @setting(
        4,
        x_center="v[]",
        y_center="v[]",
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
                Full scan range in x/y
            num_steps: int
                Number of steps the break the x/y range into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
        """

        half_scan_range = scan_range / 2

        x_low = x_center - half_scan_range
        x_high = x_center + half_scan_range

        x_voltages = numpy.linspace(x_low, x_high, num_steps)
        y_voltages = numpy.full(num_steps, y_center)
        z_voltages = numpy.full(num_steps, z_center)

        voltages = numpy.vstack((x_voltages, y_voltages, z_voltages))

        self.load_stream_writer_xyz(c, "Piezo_stage-load_scan_x", voltages, period)

        return x_voltages

    @setting(
        5,
        x_center="v[]",
        y_center="v[]",
        z_center="v[]",
        scan_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]",
    )
    def load_scan_y(self, c, x_center, y_center, z_center, scan_range, num_steps, period):
        """Load a scan that will step through scan_range in y keeping x and y 
        constant at its center.

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center y voltage of the scan
            z_center: float
                Center z voltage of the scan
            scan_range: float
                Full scan range in x/y
            num_steps: int
                Number of steps the break the x/y range into
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
        y_voltages = numpy.linspace(y_low, y_high, num_steps)
        z_voltages = numpy.full(num_steps, z_center)

        voltages = numpy.vstack((x_voltages, y_voltages, z_voltages))

        self.load_stream_writer_xyz(c, "Piezo_stage-load_scan_y", voltages, period)

        return y_voltages
    
    @setting(
        55,
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
                Full scan range in z
            num_steps: int
                Number of steps the break the x/y range into
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

        self.load_stream_writer_xyz(c, "Piezo_stage-load_scan_y", voltages, period)

        return z_voltages

    @setting(6, x_points="*v[]", y_points="*v[]", period="i")
    def load_arb_scan_xy(self, c, x_points, y_points, period):
        """Load a scan that goes between points. E.i., starts at [1,1] and
        then on a clock pulse, moves to [2,1]. Can work for arbitrarily large
        number of points 
        (previously load_two_point_xy_scan)

        Params
            x_points: list(float)
                X values correspnding to positions in x
                y_points: list(float)
                Y values correspnding to positions in y
            period: int
                Expected period between clock signals in ns

        """

        voltages = numpy.vstack((x_points, y_points))

        self.load_stream_writer_xy(c, "Piezo_stage-load_arb_scan_xy", voltages, period)

        return



__server__ = PosXyzPi6163c()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
