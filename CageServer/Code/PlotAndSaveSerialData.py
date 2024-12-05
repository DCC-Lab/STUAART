"""Serial Communication and Real-Time Data Plotting from Arduino.

This module defines the "SerialAnalyser" class, which handles serial
communication from an Arduino device and plots weight sensor data
in real-time. The real-time data is plotted using Matplotlib's "FuncAnimation"
and can be optimized for rendering efficiency by using the "optimize=True"
option. The class also provides functionality to send commands to the Arduino
and capture user input in a non-blocking manner. It can also log data to a file
in real-time, ensuring that the user can interact with the Arduino even during
data collection and plotting.

Classes
-------
SerialAnalyser
    A class for handling serial communication and real-time data plotting.

Usage
-----
For sake of organization, it's strongly recommended to use the PlateformIO
environment for embeded developpment such as Arduino. PlateformIO is available
as a VSCode extension and free to use.

To use the "SerialAnalyser", an Arduino sketch first has to be uploaded to the
board. Then, instantiate the class with the appropriate serial port (has shown
at the end of this script) and run the program:

    analyser = SerialAnalyser(port="COM10", file_name="data_log.txt")
    analyser.run(plot_enabled=True)

Options
-------
plot_enabled : bool
    Wether or not to activate real-time plotting feature, defaults to False.
save : bool
    Whether or not to save the data to a file, defaults to False.
file_name : str or None
    The file path where data should be saved (if "save" is True).
optimize : bool
    If True, uses Matplotlib's blit optimization for rendering the plot,
    defaults to False. WARNING: axis labels are not going to be dynamically
    updated in this mode.

Notes
-----
This script handles exceptions like file-saving errors (if an invalid file
path is provided) and serial communication errors.

Known issues
------------
When using plot_enabled=True, the SerialAnalyser class uses regular expression
to identify the begining of data output and extract the values as floats. It
works this way to accomodate the "calibration phase" where the user is prompt
to interact with the console at the begining of the Arduino program. However,
if you close this script and reopen it while still having an object on the load
cell, the Arduino will still be sending data for a few moments before restarting
itself (to callibration phase). To avoid any errors, make sure that you close
this script, remove all object from the loadcell, upload the sketch again, and
start this script afterwards. This procedure will make sure the serial
communication always start at the begining of the Arduino sketch.

"""

# Future import
from __future__ import annotations

__all__ = "SerialAnalyser",
__version__ = "1.0"
__author__ = "Maxime Tousignant-Tremblay"

# Std library
import re
import sys
import time
import queue
import serial
import typing
import threading
from pathlib import Path, WindowsPath

# Third-party libraries
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


THISDIR = Path(__file__).parent


class SerialAnalyser(serial.Serial):
    """Class to handle serial communication from an Arduino and real-time
    data plotting, inheriting from serial.Serial.

    Attributes
    ----------
    weight : list
        Stores the weight sensor values for plotting.
    time : list
        Stores the time values for plotting.
    cmd_queue : queue.Queue
        A queue to store user commands for sending to Arduino.
    start_time : float
        The time when the data collection started.
    title : str
        Stores the real-time plot title.

    Methods
    -------
    extract_value(input_str):
        Extracts a float from a string using regex.
    read_serial_data():
        Reads data from the serial connection.
    send_data_to_arduino(data):
        Sends a command to the Arduino.
    handle_cmd_input():
        Captures user input for commands in a separate thread.
    update_plot(frame):
        Updates the real-time plot.
    start_plotting():
        Starts real-time data plotting.
    run(plot_enabled=False):
        Main method to run the program with or without plotting.

    """

    __slots__ = (
    )

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        save: bool = True,
        file_name: typing.Optional[str] = None,
        optimize: bool = False,
        title: typing.Optional[str] = None,
        plot_enabled: bool = True,
        timer: typing.Optional[int | float] = None,
    ) -> SerialAnalyser:
        """Initializes the SerialAnalyser object and connects to serial port.

        Parameters
        ----------
        port : str
            The COM port or device path to connect (e.g., "COM3" or "/dev/ttyUSB0").
        baudrate : int, optional
            The baud rate for the serial communication, defaults to 115200.
        save : bool
            Wether or not to save the data to a file, defaults to true.
            Requires the parameter "file_name" to be defined.
        file_name : str, optional
            The name, extension and location of the file to save (e.g.,
            "/path/to/folder/data.txt").
        optimize : bool
            When True, pass argument blit=True to matplotlib's FuncAnimation
            function for more efficient rendering. However, ticks label are not
            dynamically updated in this mode. It becomes equivalent to plotting
            weight(time) data without axis label. This setting is only
            recommended for short tests where only the curve shape is relevant.
            Data saving is not affected by this parameter.
        title : str, optional
            The title to give to the real-time plot.
        timer : int, float, optional
            Set a timer, in minutes, to record/plot data.

        """
        super().__init__(port=port, baudrate=baudrate, timeout=1)
        self.save = save
        self.optimize = optimize
        self.file_name = file_name
        self.plot_enabled = plot_enabled
        self.timer = timer

        self.weight = []
        self.time = []
        self.cmd_queue = queue.Queue()
        self.start_time = time.time() / 60  # Start time in min

        if title is None:
            self.title = "Real-time Weight Data from Arduino"
        else:
            self.title = title

        target_loc = None
        if self.file_name is not None:
            target_loc = Path(self.file_name).parent

        # Handles common errors regarding data saving
        if self.save and self.file_name is None:
            raise ValueError(
                "The 'file_name' parameter is required to save the data"
            )
        elif target_loc is not None and not target_loc.is_dir():
            raise NotADirectoryError(
                f"{target_loc} is not a valid location to save data"
            )
        elif self.save and Path(self.file_name).is_file():
            raise FileExistsError(
                "You're about to overwrite an existing data file!"
            )
        elif self.save:
            with open(self.file_name, "a") as f:
                f.write(f"elapsed_time [s],weight [g]\n")

    @staticmethod
    def extract_value(input_str: str) -> float | None:
        """Extracts the last float value from a given string.

        Parameter
        ---------
        input_str : str
            The input string to extract the float value from.

        Returns
        -------
        float or None
            The extracted float value or None if no valid number is found.

        """
        pattern = r"[-+]?\d*\.\d+|\d+"
        matches = re.findall(pattern, input_str)
        try:
            value = float(matches[-1])  # Use the last number in the string
            return value

        except (IndexError, ValueError) as err:
            print(f"\33[93mError extracting value: {err}\033[0m")
            return

    def read_serial_data(self) -> float | None :
        """Reads a single line from the serial and extracts the value.

        Returns
        -------
        float or None
            The extracted value as a float if available, None otherwise.

        """
        try:
            line = self.readline().decode('utf-8').strip()
            if line:
                print(f"Serial Output: {line}")
                if "Weight LoadCell" in line:
                    value = self.extract_value(line)
                    if self.save:
                        current_time = time.time() / 60
                        elapsed_time = current_time - self.start_time
                        with open(self.file_name, "a") as f:
                            f.write(f"{elapsed_time},{value}\n")
                    return value
                return
            return

        except Exception as err:
            print(f"Error reading from serial: {err}")
            return

    def send_data_to_arduino(self, cmd: str) -> None:
        """Sends a command to the Arduino via the serial connection.

        Parameter
        ---------
        data : str
            The commandto send to the Arduino.

        """
        self.write(f"{cmd}\n".encode('utf-8'))

    def handle_cmd_input(self) -> None:
        """Continuously captures user input and sends it to the command queue."""
        try:
            while True:
                cmd = input()
                self.cmd_queue.put(cmd)

        except (KeyboardInterrupt, EOFError):
            self.__exit__()

    def update_plot(self, frame: int, ax: plt.Axes) -> tuple[plt.Line2D, ...]:
        """Updates the real-time plot with data read from the serial connection.

        Parameters
        ----------
        frame : int
            The current animation frame (required by FuncAnimation). WARNING:
            this parameter must remain an argument even if unsed.
        ax : matplotlib.pyplot.Axes
            The axes object for updating the plot.

        Returns
        -------
        line : tuple
            Iterable containing artist objects that were drawn
            (for FuncAnimation).

        """
        weight = self.read_serial_data()

        # Arduino outputs weight data
        if weight is not None:
            current_time = time.time() / 60
            elapsed_time = current_time - self.start_time

            self.time.append(elapsed_time)
            self.weight.append(weight)

            # Clear and update the plot data
            ax.clear()
            line, = ax.plot(self.time, self.weight, "b")
            ax.set_xlabel("Time [min]")
            ax.set_ylabel("Weight [g]")
            ax.set_title(self.title)

            # Autoscale x and y axis to fit all the data
            ax.relim()
            ax.autoscale_view(True, True, True)
            return line,

        # In this case, user has to input cmds
        elif not self.cmd_queue.empty():
            cmd = self.cmd_queue.get()
            self.send_data_to_arduino(cmd)

    def start_plotting(self) -> None:
        """Starts real-time data plotting."""
        plt.style.use(f"{THISDIR}/LabReport.mplstyle")
        fig, ax = plt.subplots()
        if self.optimize:
            _ = FuncAnimation(
                fig,
                self.update_plot,
                fargs=(ax,),
                interval=20,
                blit=True,
                cache_frame_data=False,
            )
        else:
            _ = FuncAnimation(
                fig,
                self.update_plot,
                fargs=(ax,),
                interval=20,
                cache_frame_data=False,
            )
        plt.show()

    def run(self) -> None:
        """Main method to run the program with or without plotting.

        Parameters
        ----------
        plot_enabled : bool
            Whether to enable real-time plotting, by default False.
        title : str
            Adds a title to the real-time plot, defaults to no title.

        """
        # Start a thread to handle user input commands
        cmd_thread = threading.Thread(target=self.handle_cmd_input, daemon=True)
        cmd_thread.start()

        try:
            while True:
                # Process any commands in the queue
                if not self.cmd_queue.empty():
                    cmd = self.cmd_queue.get()
                    self.send_data_to_arduino(cmd)

                # Read and print serial data
                weight = self.read_serial_data()

                if self.plot_enabled is True and weight is not None:
                    self.start_plotting()

        except (KeyboardInterrupt, EOFError):
            self.__exit__()

    def __enter__(self) -> None:
        return self

    def __exit__(self, *args) -> None:
        self.close()
        print("\nExiting...")
        sys.exit(0)


if __name__ == "__main__":
    # Generating file names based on current date (e.g 20240923)
    today = time.localtime()
    today = time.strftime("%Y%m%d%H%M", today)
    # file_name = THISDIR.joinpath(f"sessions/{today}/data/{today}_FireBeetleClock.txt").as_posix()
    file_name = THISDIR.joinpath(f"SpikesData/{today}_FireBeetleClock.txt").as_posix()
    # Replace "COM10" with your system's correct port
    # Set plot_enabled=True to enable plotting
    with SerialAnalyser(port="COM9", save=True, file_name=file_name, plot_enabled=False) as sa:
    # with SerialAnalyser(port="COM8", file_name=file_name) as sa:
        sa.run()