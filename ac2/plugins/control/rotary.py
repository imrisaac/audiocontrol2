'''
Copyright (c) 2019 Modul 9/HiFiBerry
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import logging
from typing import Dict

from usagecollector.client import report_usage

from ac2.plugins.control.controller import Controller

import colorsys
import time
import threading
import qwiic_micro_oled
import sys

import ioexpander as io

from pyky040 import pyky040

class Rotary(Controller):

    def __init__(self, params: Dict[str, str]=None):
        super().__init__()
        
        self.clk = 4
        self.dt = 17
        self.sw = 27
        self.step = 5

        self.I2C_ADDR = 0x0F  # 0x18 for IO Expander, 0x0F for the encoder breakout

        self.PIN_RED = 1
        self.PIN_GREEN = 7
        self.PIN_BLUE = 2

        self.POT_ENC_A = 12
        self.POT_ENC_B = 3
        self.POT_ENC_C = 11

        self.BRIGHTNESS = 0.5                # Effectively the maximum fraction of the period that the LED will be on
        self.PERIOD = int(255 / self.BRIGHTNESS)  # Add a period large enough to get 0-255 steps at the desired brightness

        self.ioe = io.IOE(i2c_addr=self.I2C_ADDR, interrupt_pin=4)

        # Swap the interrupt pin for the Rotary Encoder breakout
        if self.I2C_ADDR == 0x0F:
            self.ioe.enable_interrupt_out(pin_swap=True)

        self.ioe.setup_rotary_encoder(1, self.POT_ENC_A, self.POT_ENC_B, pin_c=self.POT_ENC_C)

        self.ioe.set_pwm_period(self.PERIOD)
        self.ioe.set_pwm_control(divider=2)  # PWM as fast as we can to avoid LED flicker

        self.ioe.set_mode(self.PIN_RED, io.PWM, invert=True)
        self.ioe.set_mode(self.PIN_GREEN, io.PWM, invert=True)
        self.ioe.set_mode(self.PIN_BLUE, io.PWM, invert=True)

        self.myOLED = qwiic_micro_oled.QwiicMicroOled()

        if not self.myOLED.connected:
            print("The Qwiic Micro OLED device isn't connected to the system. Please check your connection", \
                file=sys.stderr)
            return

        self.myOLED.begin()
        #  clear(ALL) will clear out the myOLED's graphic memory.
        #  clear(PAGE) will clear the Arduino's display buffer.
        self.myOLED.clear(self.myOLED.ALL)  #  Clear the display's memory (gets rid of artifacts)
        #  To actually draw anything on the display, you must call the
        #  display() function.
        self.myOLED.display()
        self.myOLED.set_font_type(3)  # Set font type 1 which is 5x7 pixel font

        self.myOLED.clear(self.myOLED.PAGE)  #  Clear the display's buffer

        self.name = "rotary"
        
        if params is None:
            params={}
        
        if "clk" in params:
            try:
                self.clk = int(params["clk"])
            except:
                logging.error("can't parse %s",params["clk"])
            

        if "dt" in params:
            try:
                self.dt = int(params["dt"])
            except:
                logging.error("can't parse %s",params["dt"])

        if "sw" in params:
            try:
                self.sw = int(params["sw"])
            except:
                logging.error("can't parse %s",params["sw"])
                
        if "step" in params:
            try:
                self.step = int(params["step"])
            except:
                logging.error("can't parse %s",params["step"])
                
        logging.info("initializing rotary controller on GPIOs "
                     " clk=%s, dt=%s, sw=%s, step=%s%%",
                     self.clk, self.dt, self.sw, self.step)

        self.encoder = pyky040.Encoder(CLK=self.clk, DT=self.dt, SW=self.sw)
        self.encoder.setup(scale_min=0, 
                           scale_max=100, 
                           step=1, 
                           inc_callback=self.increase, 
                           dec_callback=self.decrease, 
                           sw_callback=self.button)
            
    def increase(self,val):
        if self.volumecontrol is not None:
            self.volumecontrol.change_volume_percent(self.step)
            report_usage("audiocontrol_rotary_volume", 1)
        else:
            logging.info("no volume control, ignoring rotary control")

    def decrease(self,val):
        if self.volumecontrol is not None:
            self.volumecontrol.change_volume_percent(-self.step)
            report_usage("audiocontrol_rotary_volume", 1)
        else:
            logging.info("no volume control, ignoring rotary control")

    def button(self):
        if self.playercontrol is not None:
            self.playercontrol.playpause()
            report_usage("audiocontrol_rotary_button", 1)
        else:
            logging.info("no player control, ignoring press")
    
    def loop(self):
        while True:
            count = 0
            if self.ioe.get_interrupt():
                count = self.ioe.read_rotary_encoder(1)
                self.ioe.clear_rotary_encoder(1)
                self.ioe.clear_interrupt()

            h = (count % 360) / 360.0
            r, g, b = [int(c * self.PERIOD * self.BRIGHTNESS) for c in colorsys.hsv_to_rgb(h, 1.0, 1.0)]
            self.ioe.output(self.PIN_RED, r)
            self.ioe.output(self.PIN_GREEN, g)
            self.ioe.output(self.PIN_BLUE, b)

            #logging.info("count: %s, %s, %s, %s", count, r, g, b)
            time.sleep(1.0 / 30)

            if count < 0:
                self.decrease(-5)
            elif count > 0:
                self.increase(5)

            self.myOLED.clear(self.myOLED.PAGE)  #  Clear the display's buffer
            self.myOLED.set_cursor(0, 0)  #  Set the cursor to x=0, y=0
            self.myOLED.print(self.volumecontrol.current_volume())  #  Add "Hello World" to buffer

            #  To actually draw anything on the display, you must call the display() function. 
            self.myOLED.display()

    
    def run(self):
        new_thread = threading.Thread(target=self.loop)
        new_thread.start()
