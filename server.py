from audiomanager import AudioManager
from offcharger import OffCharger
from powerplant import PowerPlant
from aiohttp import web
from motorcontroller import MotorController
from servocontroller import ServoController
from lightscontroller import LightsController
from heartbeat import Heartbeat
from speaker import enableSpeaker
from subprocess import call
import os
import pigpio
from configparser import ConfigParser
from alsa import Alsa
import ssl
import sys
from externalrunner import ExternalProcess
import asyncio
from januseventhandler import JanusEventHandler
from tts import TTSSpeaker
from startupSequence import StartupSequenceController
from followmode import FollowMode

routes = web.RouteTableDef()

motorController = None
servoController = None
heartbeat = None
signalingServer = None
alsa = None
tts = None
powerPlant = None
startupController = None
audioManager = None
audioManagerThread = None
janusEventHandler = None
offCharger = None
cameraHub = None
followMode = None


@routes.get("/")
async def getPageHTML(request):
    return web.FileResponse("index.html")


@routes.post("/sendCommand")
async def setCommand(request):
    commandObj = await request.json()
    newBearing = commandObj['bearing']
    newLook = commandObj['look']
    newSlow = commandObj['slow']

    if followMode is not None and followMode.isEnabled():
        # Key releases send an all-stop command; only real input takes the controls back from follow mode.
        if newBearing == "0" and newLook == 0:
            return web.Response(text="OK")
        followMode.disable("manual control")

    if newBearing in MotorController.validBearings:
        motorController.setBearing(newBearing, newSlow)
    else:
        print("Invalid bearing {}".format(newBearing))
        return web.Response(status=400, text="Invalid")

    if newLook == 0:
        await servoController.lookStop()
    elif newLook == -1:
        await servoController.forward()
    elif newLook == 1:
        await servoController.backward()
    else:
        print("Invalid look at {}".format(newLook))
        return web.Response(status=400, text="Invalid")

    return web.Response(text="OK")


@routes.post("/shutDown")
async def shutDown(request):
    call("sudo halt", shell=True)


@routes.post("/restart")
async def restart(request):
    call("sudo reboot", shell=True)


@routes.post("/sendTTS")
async def sendTTS(request):
    ttsObj = await request.json()
    ttsString = ttsObj['str']
    tts.sayText(ttsString)
    return web.Response(text="OK")


@routes.post("/setVolume")
async def setVolume(request):
    volumeObj = await request.json()
    volume = int(volumeObj['volume'])
    alsa.setVolume(volume)
    return web.Response(text="OK")


@routes.post("/heartbeat")
async def onHeartbeat(request):
    stats = heartbeat.onHeartbeatReceived()
    return web.json_response(stats)


@routes.get("/follow")
async def getFollowStatus(request):
    if followMode is None:
        return web.json_response({"available": False})
    return web.json_response(dict(followMode.status(), available=True))


@routes.post("/follow")
async def setFollow(request):
    if followMode is None:
        return web.json_response(
            {"available": False, "error": "Follow mode needs CameraSource=picamera2 in rover.conf"}, status=409)

    followObj = await request.json()
    if bool(followObj['enabled']):
        followMode.enable()
    else:
        followMode.disable()
    return web.json_response(dict(followMode.status(), available=True))


@routes.post("/lights")
async def onLights(request):
    lightsObj = await request.json()
    on = bool(lightsObj['on'])
    if on:
        lightsController.lightsOn()
    else:
        lightsController.lightsOff()
    return web.Response(text="OK")


async def onJanusEvent(request):
    try:
        eventObj = await request.json()
        janusEventHandler.handleEvent(eventObj)
    except Exception as e:
        print('Error handling janus event: {}'.format(e))
    finally:
        return web.Response(text="OK")


# Python 3.7 is overly wordy about self-signed certificates, so we'll suppress the error here
def loopExceptionHandler(loop, context):
    exception = context.get('exception')
    if isinstance(exception, ssl.SSLError) and exception.reason == 'SSLV3_ALERT_CERTIFICATE_UNKNOWN':
        pass
    else:
        loop.default_exception_handler(context)


def createSSLContext(homePath):
    # Create an SSL context to be used by the websocket server
    print('Using TLS with keys in {!r}'.format(homePath))
    chain_pem = os.path.join(homePath, 'cert.pem')
    key_pem = os.path.join(homePath, 'key.pem')
    sslctx = ssl.create_default_context()

    try:
        sslctx.load_cert_chain(chain_pem, keyfile=key_pem)
    except FileNotFoundError:
        print("Certificates not found, did you run generate_cert.sh?")
        sys.exit(1)
    # FIXME
    sslctx.check_hostname = False
    sslctx.verify_mode = ssl.CERT_NONE
    return sslctx


runners = []


async def start_site(app, address, port, sslContext=None):
    runner = web.AppRunner(app)
    runners.append(runner)
    await runner.setup()

    if sslContext is not None:
        site = web.TCPSite(runner, host=address, port=port, ssl_context=sslContext)
    else:
        site = web.TCPSite(runner, host=address, port=port)

    #site = web.TCPSite(runner, host=address, port=port)

    await site.start()


if __name__ == "__main__":
    homePath = os.path.dirname(os.path.abspath(__file__))
    sslctx = createSSLContext(os.path.dirname(homePath))

    #gpio = pigpio.pi()
    #if not gpio.connected:
    #    print('GPIO not connected')
    #    exit()

    config = ConfigParser()
    config.read(os.path.join(homePath, "rover.conf"))
    audioConfig = config["AUDIO"]
    videoConfig = config["VIDEO"]

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(loopExceptionHandler)

    audioManager = AudioManager(config)

    motorController = MotorController(config, audioManager)

    alsa = Alsa(config)

    servoController = ServoController(config, audioManager)
    lightsController = LightsController(config)

    enableSpeaker()
    tts = TTSSpeaker(config, alsa, audioManager)

    powerPlant = PowerPlant()

    startupController = StartupSequenceController(config, servoController, lightsController, tts)

    heartbeat = Heartbeat(config, servoController, motorController, alsa, lightsController, powerPlant)

    offCharger = OffCharger(config, tts, motorController)

    janus = ExternalProcess(videoConfig["JanusStartCommand"], False, False, "janus.log")

    # picamera2: the server owns the camera, streams it and can run follow mode.
    # external: the GStreamerStartCommand script owns the camera (video only, no follow mode).
    videoStream = None
    if videoConfig.get("CameraSource", "picamera2") == "picamera2":
        try:
            from camerahub import CameraHub
            from colordetector import ColorDetector

            cameraHub = CameraHub(videoConfig)
            cameraHub.start()
            followConfig = config["FOLLOW"] if config.has_section("FOLLOW") else {}
            followMode = FollowMode(followConfig, cameraHub, ColorDetector(followConfig), motorController,
                                    servoController, heartbeat, powerPlant)
        except Exception as e:
            print("Could not start the camera with picamera2, falling back to GStreamerStartCommand: {}".format(e))
            if cameraHub is not None:
                try:
                    cameraHub.stop()
                except Exception as stopError:
                    print("Could not release the camera: {}".format(stopError))
            cameraHub = None
            followMode = None

    if cameraHub is None:
        videoStream = ExternalProcess(videoConfig["GStreamerStartCommand"], False, False, "video.log")

    janusEventHandler = JanusEventHandler()

    mainApp = web.Application()
    mainApp.add_routes(routes)
    mainApp.router.add_static('/js/', path=os.path.join(homePath, 'js'))
    loop.create_task(start_site(mainApp, '0.0.0.0', 5000, None))

    eventListenerApp = web.Application()
    eventListenerApp.add_routes([web.post('/janusEvent', onJanusEvent)])
    loop.create_task(start_site(eventListenerApp, 'localhost', 5001))

    try:
        loop.run_forever()
    except:
        pass
    finally:
        if followMode is not None:
            followMode.disable("shutting down")
        servoController.stop()
        lightsController.stop()
        #gpio.stop()
        janus.endProcess()
        if cameraHub is not None:
            cameraHub.stop()
        if videoStream is not None:
            videoStream.endProcess()
        for runner in runners:
            loop.run_until_complete(runner.cleanup())