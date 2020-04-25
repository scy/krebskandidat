# Krebskandidat

**This is a work in progress. No pull requests yet, please, and don’t depend on this code for anything. The documentation is also severely lacking. This will be fixed.**

The goal of this project is to build a custom particulate sensor to alert me when someone is smoking below my balcony.

## Pins

In my setup, I’m using these pins:

* 12: input, pull down; connected to a reed switch to sense whether the balcony door is open or closed
* 13: set to be permanently high (heh); provides 3.3V for sensing whether the door is closed

## Links

* [BitBastelei #232](https://youtu.be/VVlLjSdvaYI) using the sensor with custom low-level code (in German)
* [alexmrqt/micropython-sds011](https://github.com/alexmrqt/micropython-sds011) is a simple MicroPython library to talk to the SDS011 sensor
* [gitlab:frankrich/sds011_particle_sensor](https://gitlab.com/frankrich/sds011_particle_sensor), a Python 3 library with advanced features like work cycles, but not the most beautiful code
* [ssube/prometheus_express](https://github.com/ssube/prometheus_express), a MicroPython compatible Prometheus client library (but it apparently doesn’t provide timestamps)
