from neopixel import *
import time

class GELight:
    #constructor
    def __init__(self):
        # LED strip configuration:
        self.LED_COUNT      = 75      # Number of LED pixels.
        self.LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
        self.LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
        self.LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        

        # Create NeoPixel object with appropriate configuration.
        self.strip = Adafruit_NeoPixel(self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS)
        self.strip.begin()

    def setRed(self):
        for i in range(self.strip.numPixels()):
                self.strip.setPixelColorRGB(i, 255, 0, 0)
        self.strip.show()
                #time.sleep(5/1000)


    def setGreen(self):
            for i in range(self.strip.numPixels()):
                    self.strip.setPixelColorRGB(i, 0, 255, 0)
            self.strip.show()


    def setYellow(self):
            
            for i in range(self.strip.numPixels()):
                    self.strip.setPixelColorRGB(i, 255, 255, 0)
            self.strip.show()

    def setOff(self):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0,0,0))
        self.strip.show()

    def setWhite(self):
	for i in range(self.strip.numPixels()):
	    self.strip.setPixelColorRGB(i, 255, 255, 255)
	self.strip.show()

    def setRainbow(self, wait_ms=20, iterations=5):
	"""Draw rainbow that uniformly distributes itself across all pixels."""
	for j in range(256*iterations):
                #print(j)
		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, self.wheel((int(i * 256 / self.strip.numPixels()) + j) & 255))
                self.strip.show()
		time.sleep(wait_ms/1000.0)


    def setWheel(self, pos):
            """Generate rainbow colors across 0-255 positions."""
            if pos < 85:
                    return Color(pos * 3, 255 - pos * 3, 0)
            elif pos < 170:
                    pos -= 85
                    return Color(255 - pos * 3, 0, pos * 3)
            else:
                    pos -= 170
                    return Color(0, pos * 3, 255 - pos * 3)
