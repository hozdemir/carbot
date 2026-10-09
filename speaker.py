def enableSpeaker():
    """Switches on the Fusion HAT speaker. It starts switched off on every boot (and `fusion_hat test_speaker` switches
    it off again when it finishes), so without this the rover makes no sound. Returns whether it worked; failures
    only cost the sound, so they are logged instead of stopping the server."""
    try:
        from fusion_hat.device import enable_speaker

        enable_speaker()
        print("Fusion HAT speaker enabled")
        return True
    except PermissionError as e:
        print("Could not enable the Fusion HAT speaker, no permission to write {}. Run the server as a user that can, "
              "or run `fusion_hat enable_speaker` as root before starting it.".format(e.filename))
    except Exception as e:
        print("Could not enable the Fusion HAT speaker: {}".format(e))
    return False
