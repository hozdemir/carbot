import subprocess

import cv2


class CameraHub:
    """Owns the Pi camera so streaming and follow mode can share it: libcamera lets only one process open the camera.

    The main stream is H.264 encoded in hardware and piped through GStreamer into the Janus streaming plugin (the same
    RTP-over-UDP feed video.sh produced). A small lores stream with the same 16:9 field of view is kept for computer
    vision and read on demand with captureFrame().
    """

    def __init__(self, videoConfig):
        self.width = int(videoConfig.get("Width", 1280))
        self.height = int(videoConfig.get("Height", 720))
        self.framerate = int(videoConfig.get("Framerate", 30))
        self.bitrate = int(videoConfig.get("Bitrate", 4000000))
        self.visionWidth = int(videoConfig.get("VisionWidth", 320))
        self.visionHeight = int(videoConfig.get("VisionHeight", 180))
        self.streamHost = videoConfig.get("StreamHost", "127.0.0.1")
        self.streamPort = int(videoConfig.get("StreamPort", 8004))

        self.picam2 = None
        self.streamer = None

    def start(self):
        # Imported here so the rest of the server, and the tests, do not need picamera2 installed.
        from picamera2 import Picamera2
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import FileOutput

        self.picam2 = Picamera2()
        configuration = self.picam2.create_video_configuration(
            main={"size": (self.width, self.height)},
            # The Pi 4 / CM4 ISP only produces YUV420 on the lores stream.
            lores={"size": (self.visionWidth, self.visionHeight), "format": "YUV420"},
            controls={"FrameRate": self.framerate},
        )
        self.picam2.configure(configuration)

        self.streamer = subprocess.Popen(
            [
                "gst-launch-1.0", "fdsrc", "do-timestamp=true",
                "!", "h264parse", "config-interval=1",
                "!", "rtph264pay", "pt=96", "config-interval=1",
                "!", "udpsink", "host={}".format(self.streamHost), "port={}".format(self.streamPort),
            ],
            stdin=subprocess.PIPE,
        )

        # repeat=True resends SPS/PPS with every keyframe so viewers that join late can start decoding.
        encoder = H264Encoder(bitrate=self.bitrate, repeat=True, iperiod=self.framerate)
        self.picam2.start_recording(encoder, FileOutput(self.streamer.stdin))
        print("Camera streaming {}x{}@{} to {}:{}, vision frames {}x{}".format(
            self.width, self.height, self.framerate, self.streamHost, self.streamPort,
            self.visionWidth, self.visionHeight))

    def captureFrame(self):
        """Returns the latest lores frame as a BGR image. Blocks until a frame is ready, so call it off the event
        loop."""
        yuv = self.picam2.capture_array("lores")
        # With these buffers COLOR_YUV420p2BGR yields red-green-blue order (picamera2's own Qt preview shows its result
        # as RGB888), which made orange wood look blue. The *2RGB conversion gives the blue-green-red order OpenCV uses.
        bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV420p2RGB)
        # Drop any row padding (stride) beyond the configured width.
        return bgr[:, :self.visionWidth]

    def stop(self):
        if self.picam2 is not None:
            try:
                self.picam2.stop_recording()
            finally:
                self.picam2.close()
                self.picam2 = None
        if self.streamer is not None:
            self.streamer.terminate()
            self.streamer = None
