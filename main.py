import atexit
import math
import cv2
from picamera2 import Picamera2
import time
import numpy as np
from adafruit_servokit import ServoKit
import PID

direction_pid = PID.PositionalPID(0.8, 0, 0.2)
yservo_pid = PID.PositionalPID(0.8, 0.2, 0.8)
xservo_pid = PID.PositionalPID(1.1, 0.2, 0.8)

speed_pid = PID.PositionalPID(2.1, 0, 0.2)

# PCA9685 sürücüsünü ayarla
kit = ServoKit(channels=16)

picam2 = Picamera2()

# Başlangıç açılarını ortada ayarla
panAngle = 90
tiltAngle = 90

# Servo açılarını ayarla
kit.servo[0].angle = panAngle
kit.servo[1].angle = tiltAngle

dispW = 320
dispH = 240
picam2.preview_configuration.main.size = (dispW, dispH)
picam2.preview_configuration.main.format = "RGB888"
picam2.preview_configuration.controls.FrameRate = 30
picam2.preview_configuration.align()
picam2.configure("preview")
picam2.start()

# Mavi tonları için HSV renk aralığı
hueLow = 100
hueHigh = 140
satLow = 150
satHigh = 255
valLow = 50
valHigh = 255


def disable_servos():
    # Tüm servoları döngüye al ve sinyali kes
    for i in range(16):
        kit.servo[i].fraction = None


atexit.register(disable_servos)
atexit.register(picam2.stop)

while True:
    frame = picam2.capture_array()
    frame_ = cv2.GaussianBlur(frame, (5, 5), 0)
    frameHSV = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lowerBound = np.array([hueLow, satLow, valLow])
    upperBound = np.array([hueHigh, satHigh, valHigh])
    mask = cv2.inRange(frameHSV, lowerBound, upperBound)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    myMask = cv2.inRange(frameHSV, lowerBound, upperBound)

    contours = cv2.findContours(myMask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]

    if len(contours) > 0:
        cnt = max(contours, key=(cv2.contourArea))
        (color_x, color_y), color_radius = cv2.minEnclosingCircle(cnt)
        if color_radius > 10:
            cv2.circle(frame, (int(color_x), int(color_y)), int(color_radius), (255, 0, 255), 2)
            if math.fabs(150 - color_x) > 10:
                xservo_pid.SystemOutput = color_x
                xservo_pid.SetStepSignal(150)
                xservo_pid.SetInertiaTime(0.01, 0.1)
                target_valuex = int(1500 + xservo_pid.SystemOutput)
                target_servox = int((target_valuex - 500) / 10)
                if target_servox > 180:
                    target_servox = 180
                if target_servox < 0:
                    target_servox = 0
                kit.servo[0].angle = target_servox
            if math.fabs(150 - color_y) > 10:
                yservo_pid.SystemOutput = color_y
                yservo_pid.SetStepSignal(150)
                yservo_pid.SetInertiaTime(0.01, 0.1)
                target_valuey = int(1500 - yservo_pid.SystemOutput)
                target_servoy = int((target_valuey - 500) / 10)
                if target_servoy > 180:
                    target_servoy = 180
                if target_servoy < 0:
                    target_servoy = 0
                #kit.servo[0].angle = target_servoy

    time.sleep(0.01)