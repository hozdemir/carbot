rpicam-vid -t 0 --inline \
  --width 1280 --height 720 \
  --framerate 30 \
  --bitrate 4000000 \
  --profile high --intra 30 \
  --codec h264 -o - \
| gst-launch-1.0 -v fdsrc do-timestamp=true ! \
  h264parse config-interval=1 ! \
  rtph264pay pt=96 config-interval=1 ! \
  udpsink host=127.0.0.1 port=8004