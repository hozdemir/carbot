var up = false;
var down = false;
var left = false;
var right = false;
var lookUp = false;
var lookDown = false;
var slow = false;
var lights = false;

var lastBearing = -1;
var lastLook = 0;
var lastSlow = false;

function sendKeys() {
    var bearing = "0";
    var look = 0;

    if (up) {
        if (left) {
            bearing = "nw";
        }
        else if (right) {
            bearing = "ne";
        }
        else {
            bearing = "n";
        }
    }
    else if (down) {
        if (left) {
            bearing = "sw";
        }
        else if (right) {
            bearing = "se";
        }
        else {
            bearing = "s";
        }
    }
    else if (left) {
        bearing = "w";
    }
    else if (right) {
        bearing = "e";
    }

    if (lookUp) {
        look = 1;
    }
    else if (lookDown) {
        look = -1;
    }

    if (lastBearing != bearing || lastLook != look || lastSlow != slow) {
        lastBearing = bearing;
        lastLook = look;
        lastSlow = slow;
        var commandObj = {
            'bearing': bearing,
            'look': look,
            'slow': slow,
        };

        $.ajax({
            url: '/sendCommand',
            type: "POST",
            data: JSON.stringify(commandObj),
            contentType: "application/json; charset=utf-8",
            dataType: "json"
        });
    }


}

function sendLights() {
    var lightsObj = {
        on: lights
    };
    $.ajax({
        url: '/lights',
        type: "POST",
        data: JSON.stringify(lightsObj),
        contentType: "application/json; charset=utf-8",
        dataType: "json"
    });
}

$(document).ready(function () {
    const setVolume_throttled = _.throttle(setVolume, 500, {leading: true});

    $(document).keydown(function (event) {
        if (!$("#ttsSection").is(":visible")) {
            if (event.keyCode == 83) {
                $("#ttsSection").fadeIn(200);
                $("#ttsInput").focus();
                up = false;
                down = false;
                left = false;
                right = false;
                lookUp = false;
                lookDown = false;
                sendKeys();
                event.preventDefault();
                return;
            }

            if (event.keyCode == 86) {
                unmute();
                event.preventDefault();
                return;
            }

            if (event.key === '+' || event.key === '=' || event.key === '-') {
                let currentVolume = parseInt($("div#volumeSlider input").val());

                if (event.key === '+' || event.key === '=') {
                    currentVolume = currentVolume + 5;
                }
                else {
                    currentVolume = currentVolume - 5;
                }

                if (currentVolume > 100) {
                    currentVolume = 100;
                }
                else if (currentVolume < 0) {
                    currentVolume = 0;
                }

                $("div#volumeSlider input").val(currentVolume).trigger("input");
                event.preventDefault();
                return;
            }

            if (event.keyCode == 76) {
                toggleLights();
            }

            if (event.keyCode == 70) {
                if (!event.repeat) {
                    toggleFollow();
                }
                event.preventDefault();
                return;
            }

            if (event.keyCode == 38) {
                up = true;
                event.preventDefault();
            }
            else if (event.keyCode == 40) {
                down = true;
                event.preventDefault();
            }
            else if (event.keyCode == 37) {
                left = true;
                event.preventDefault();
            }
            else if (event.keyCode == 39) {
                right = true;
                event.preventDefault();
            }
            else if (event.keyCode == 65) {
                lookDown = true;
                event.preventDefault();
            }
            else if (event.keyCode == 90) {
                lookUp = true;
                event.preventDefault();
            } else if (event.keyCode == 16) {
                slow = true;
                event.preventDefault();
            }

            sendKeys();
        }
    });

    $(document).keyup(function (event) {
        if (!$("#ttsSection").is(":visible")) {
            if (event.keyCode == 86) {
                mute();
                event.preventDefault();
                return;
            }

            if (event.keyCode == 38) {
                up = false;
                event.preventDefault();
            }
            else if (event.keyCode == 40) {
                down = false;
                event.preventDefault();
            }
            else if (event.keyCode == 37) {
                left = false;
                event.preventDefault();
            }
            else if (event.keyCode == 39) {
                right = false;
                event.preventDefault();
            }
            else if (event.keyCode == 65) {
                lookDown = false;
                event.preventDefault();
            }
            else if (event.keyCode == 90) {
                lookUp = false;
                event.preventDefault();
            } else if (event.keyCode == 16) {
                slow = false;
                event.preventDefault();
            }

            sendKeys();
        }
    });

    $("#powerButton").click(function (event) {
        $("#shutdown-confirm").dialog({
            resizable: false,
            height: "auto",
            width: "auto",
            modal: true,
            buttons: {
                "Shut Down": function () {
                    $(this).dialog("close");
                    $.ajax({
                        url: '/shutDown',
                        type: "POST"
                    });
                },
                Cancel: function () {
                    $(this).dialog("close");
                }
            }
        });
    });

    $("#resetButton").click(function (event) {
        $("#restart-confirm").dialog({
            resizable: false,
            height: "auto",
            width: "auto",
            modal: true,
            buttons: {
                "Restart": function () {
                    $(this).dialog("close");
                    $.ajax({
                        url: '/restart',
                        type: "POST"
                    });
                },
                Cancel: function () {
                    $(this).dialog("close");
                }
            }
        });
    });

    $("#infoButton").click(function (event) {
        if ($("#info").is(":visible")) {
            $("#info").fadeOut(200);
        }
        else {
            $("#info").fadeIn(200);
        }
    });

    $("#infoButton").mouseleave(function (event) {
        $("#info").fadeOut(200);
    });

    $("#ttsButton").click(function (event) {
        if ($("#ttsSection").is(":visible")) {
            $("#ttsSection").fadeOut(200);
        }
        else {
            $("#ttsSection").fadeIn(200);
            $("#ttsInput").focus();
        }
    });

    $("#ttsInput").keydown(function (event) {
        if (event.keyCode == 27) {
            //escape
            event.preventDefault();
            $("#ttsInput").val("");
            $("#ttsSection").fadeOut(200);
        }
        else if (event.keyCode == 13) {
            //enter
            event.preventDefault();
            $("#ttsSection").animate({
                bottom: '80vh',
                opacity: '0'
            }, 200, function () {
                $("#ttsSection").hide();
                $("#ttsSection").css("bottom", "200px");
                $("#ttsSection").css("opacity", "1");
            });
            sendTTS($("#ttsInput").val());
        }
    });

    $("#ttsInput").blur(function (event) {
        $("#ttsInput").val("");
        $("#ttsSection").fadeOut(200);
    });

    $("#micButton").click(function (event) {
        if (videoroomPluginHandle) {
            if (videoroomPluginHandle.isAudioMuted()) {
                unmute();
            } else {
                mute();
            }
        }
    });

    $("#lightsButton").click(function (event) {
        toggleLights();
    });

    $("#followButton").click(function (event) {
        toggleFollow();
    });

    $(window).resize(function () {
        drawFollowTarget(lastFollowStatus);
    });

    $("div#volumeSlider input").on("input", function () {
        setVolume_throttled(this.value);
    });

    $("#vid").on("play", function(e) {
        $("#playButton").hide();
    });

    $("#vid").on("pause", function(e) {
        $("#playButton").show();
    });

    $("#playButton").click(function(e) {
        $("#vid")[0].play();
    });

    doHeartbeat();

    pollFollow();

    doConnect();
});

var doInitialSet = true;
function doHeartbeat() {
    $.ajax({
        url: '/heartbeat',
        type: "POST",
        dataType: "json"
    }).done(function (data) {
        $("#wifi_ssid").text(data.SSID);
        $("#wifi_quality").text(data.Quality);
        $("#wifi_signal").text(data.Signal);
        $("#cpuUsage").text(data.CPU);
        $("#batteryPercent").text(data.BatteryPercent);
        if (data.BatteryCharging) {
            $("#batteryCharging").show();
        } else {
            $("#batteryCharging").hide();
        }

        if (doInitialSet) {
            $("div#volumeSlider input").val(data.Volume);
            lights = data.Lights;
            syncLights();
            doInitialSet = false;
        }

        if (data.InvalidState) {
            doInitialSet = true;
        }
    }).always(function () {
        setTimeout(doHeartbeat, 1000);
    });
}

function sendTTS(str) {
    $.ajax({
        url: '/sendTTS',
        type: "POST",
        data: JSON.stringify({ str }),
        contentType: "application/json; charset=utf-8",
        dataType: "json"
    });
}

function setVolume(volume) {
    $.ajax({
        url: '/setVolume',
        type: "POST",
        data: JSON.stringify({ volume }),
        contentType: "application/json; charset=utf-8",
        dataType: "json"
    });
}

function toggleLights() {
    lights = !lights;
    sendLights();
    syncLights();
}

function syncLights() {
    if (lights) {
        $("div#lightsButton > i").text("flash_on");
    } else {
        $("div#lightsButton > i").text("flash_off");
    }
}

var lastFollowStatus = null;
var followStoppedMessageUntil = 0;

function toggleFollow() {
    if (lastFollowStatus && lastFollowStatus.available === false) {
        showFollowMessage("Follow mode needs CameraSource=picamera2 in rover.conf", 4000);
        return;
    }
    var enabled = !(lastFollowStatus && lastFollowStatus.enabled);
    $.ajax({
        url: '/follow',
        type: "POST",
        data: JSON.stringify({ enabled: enabled }),
        contentType: "application/json; charset=utf-8",
        dataType: "json"
    }).done(function (status) {
        renderFollow(status);
    }).fail(function (xhr) {
        if (xhr.responseJSON) {
            renderFollow(xhr.responseJSON);
        }
    });
}

function pollFollow() {
    $.ajax({
        url: '/follow',
        type: "GET",
        dataType: "json"
    }).done(function (status) {
        renderFollow(status);
    }).always(function () {
        // Poll fast while following so the target marker keeps up, slowly otherwise to notice server-side stops.
        var following = lastFollowStatus && lastFollowStatus.enabled;
        setTimeout(pollFollow, following ? 200 : 2000);
    });
}

function renderFollow(status) {
    var wasEnabled = lastFollowStatus && lastFollowStatus.enabled;
    lastFollowStatus = status;

    $("#followButton").toggleClass("active", !!status.enabled);
    $("#followButton").toggleClass("unavailable", status.available === false);

    if (status.enabled) {
        var text = "Following: " + status.state;
        if (status.target) {
            // TargetSize in rover.conf is this value at the distance the rover should hold.
            text += " (size " + status.target.radius.toFixed(2) + ")";
        }
        $("#followStatus").text(text).show();
    } else if (wasEnabled && status.stopReason && status.stopReason !== "turned off") {
        showFollowMessage("Follow stopped: " + status.stopReason, 4000);
    } else if (Date.now() > followStoppedMessageUntil) {
        $("#followStatus").hide();
    }

    drawFollowTarget(status);
}

function showFollowMessage(message, durationMs) {
    followStoppedMessageUntil = Date.now() + durationMs;
    $("#followStatus").text(message).show();
    setTimeout(function () {
        if (Date.now() >= followStoppedMessageUntil && !(lastFollowStatus && lastFollowStatus.enabled)) {
            $("#followStatus").hide();
        }
    }, durationMs);
}

// The video keeps its aspect ratio inside the element (object-fit: contain), so find the area the picture fills.
function videoContentRect() {
    var video = $("#vid")[0];
    var rect = video.getBoundingClientRect();
    if (!video.videoWidth || !video.videoHeight) {
        return rect;
    }
    var scale = Math.min(rect.width / video.videoWidth, rect.height / video.videoHeight);
    var width = video.videoWidth * scale;
    var height = video.videoHeight * scale;
    return {
        left: rect.left + (rect.width - width) / 2,
        top: rect.top + (rect.height - height) / 2,
        width: width,
        height: height
    };
}

function drawFollowTarget(status) {
    var canvas = $("#followOverlay")[0];
    if (!status || !status.enabled || !status.target) {
        $(canvas).hide();
        return;
    }

    var area = videoContentRect();
    $(canvas).css({ left: area.left + "px", top: area.top + "px", width: area.width + "px", height: area.height + "px" }).show();
    canvas.width = Math.round(area.width);
    canvas.height = Math.round(area.height);

    var context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.lineWidth = 3;
    context.strokeStyle = status.state === "tracking" ? "#4caf50" : "#ffc107";
    context.beginPath();
    context.arc(
        status.target.x * canvas.width,
        status.target.y * canvas.height,
        Math.max(4, status.target.radius * canvas.height),
        0,
        2 * Math.PI
    );
    context.stroke();
}
