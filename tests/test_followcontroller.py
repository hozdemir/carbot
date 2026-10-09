import unittest

from detection import Detection
from followcontroller import LOST, SEARCHING, TRACKING, FollowController, FollowSettings

SETTINGS = FollowSettings(smoothing=1.0, turnKd=0.0)


def target(x=0.5, y=0.5, radius=SETTINGS.targetSize):
    return Detection(x=x, y=y, radius=radius)


class FollowControllerTest(unittest.TestCase):
    def setUp(self):
        self.controller = FollowController(SETTINGS)

    def test_holds_still_when_the_target_is_centred_at_the_target_size(self):
        command = self.controller.update(target(), now=0.0)

        self.assertEqual(command.state, TRACKING)
        self.assertEqual((command.forward, command.turn, command.tiltDelta), (0.0, 0.0, 0.0))

    def test_turns_right_towards_a_target_on_the_right(self):
        command = self.controller.update(target(x=0.75), now=0.0)

        self.assertGreater(command.turn, 0)

    def test_turns_left_towards_a_target_on_the_left(self):
        command = self.controller.update(target(x=0.25), now=0.0)

        self.assertLess(command.turn, 0)

    def test_ignores_small_horizontal_offsets(self):
        command = self.controller.update(target(x=0.5 + SETTINGS.centerDeadband / 4), now=0.0)

        self.assertEqual(command.turn, 0.0)

    def test_turn_is_limited(self):
        command = self.controller.update(target(x=1.0), now=0.0)

        self.assertAlmostEqual(command.turn, SETTINGS.maxTurn)

    def test_drives_forward_when_the_target_is_far_away(self):
        command = self.controller.update(target(radius=SETTINGS.targetSize / 2), now=0.0)

        self.assertGreater(command.forward, 0)
        self.assertLessEqual(command.forward, SETTINGS.maxForward)

    def test_backs_away_no_faster_than_max_reverse_when_the_target_is_too_close(self):
        command = self.controller.update(target(radius=SETTINGS.targetSize * 3), now=0.0)

        self.assertAlmostEqual(command.forward, -SETTINGS.maxReverse)

    def test_ignores_small_distance_changes(self):
        radius = SETTINGS.targetSize * (1 - SETTINGS.sizeDeadband / 2)

        command = self.controller.update(target(radius=radius), now=0.0)

        self.assertEqual(command.forward, 0.0)

    def test_only_turns_when_a_far_target_is_well_off_centre(self):
        command = self.controller.update(target(x=0.5 + SETTINGS.turnBeforeDrive / 2 + 0.01, radius=0.02), now=0.0)

        self.assertEqual(command.forward, 0.0)
        self.assertGreater(command.turn, 0)

    def test_drives_slower_the_further_off_centre_the_target_is(self):
        centred = FollowController(SETTINGS).update(target(radius=0.06), now=0.0)
        offset = FollowController(SETTINGS).update(target(x=0.6, radius=0.06), now=0.0)

        self.assertGreater(centred.forward, offset.forward)
        self.assertGreater(offset.forward, 0)

    def test_tilts_towards_a_target_below_centre_in_proportion_to_elapsed_time(self):
        self.controller.update(target(y=0.75), now=0.0)

        command = self.controller.update(target(y=0.75), now=0.1)

        self.assertAlmostEqual(command.tiltDelta, SETTINGS.tiltSpeed * 0.5 * 0.1)

    def test_tilt_direction_can_be_reversed(self):
        controller = FollowController(FollowSettings(smoothing=1.0, tiltDirection=-1.0))
        controller.update(target(y=0.75), now=0.0)

        command = controller.update(target(y=0.75), now=0.1)

        self.assertLess(command.tiltDelta, 0)

    def test_searches_until_the_first_detection(self):
        command = self.controller.update(None, now=0.0)

        self.assertEqual(command.state, SEARCHING)
        self.assertEqual((command.forward, command.turn), (0.0, 0.0))

    def test_holds_still_through_a_short_dropout(self):
        self.controller.update(target(x=0.8, radius=0.05), now=0.0)

        command = self.controller.update(None, now=SETTINGS.lostTimeout / 2)

        self.assertEqual(command.state, TRACKING)
        self.assertEqual((command.forward, command.turn), (0.0, 0.0))

    def test_reports_the_target_lost_after_the_timeout(self):
        self.controller.update(target(), now=0.0)

        command = self.controller.update(None, now=SETTINGS.lostTimeout + 0.01)

        self.assertEqual(command.state, LOST)
        self.assertEqual((command.forward, command.turn), (0.0, 0.0))
        self.assertIsNone(command.target)

    def test_searches_towards_the_side_the_target_was_last_seen_when_enabled(self):
        controller = FollowController(FollowSettings(smoothing=1.0, searchTurn=0.3, searchDuration=2.0))
        controller.update(target(x=0.2), now=0.0)

        searching = controller.update(None, now=controller.settings.lostTimeout + 0.5)
        givenUp = controller.update(None, now=controller.settings.lostTimeout + 2.5)

        self.assertEqual(searching.state, SEARCHING)
        self.assertAlmostEqual(searching.turn, -0.3)
        self.assertEqual(givenUp.state, LOST)
        self.assertEqual(givenUp.turn, 0.0)

    def test_picks_the_target_up_again_after_losing_it(self):
        self.controller.update(target(), now=0.0)
        self.controller.update(None, now=1.0)

        command = self.controller.update(target(x=0.8), now=1.1)

        self.assertEqual(command.state, TRACKING)
        self.assertGreater(command.turn, 0)

    def test_smooths_jumps_in_the_detected_position(self):
        controller = FollowController(FollowSettings(smoothing=0.5, turnKd=0.0))
        controller.update(target(x=0.5), now=0.0)

        command = controller.update(target(x=0.9), now=0.1)

        self.assertAlmostEqual(command.target.x, 0.7)

    def test_derivative_term_damps_a_target_returning_to_centre(self):
        controller = FollowController(FollowSettings(smoothing=1.0, turnKd=0.1))
        controller.update(target(x=0.9), now=0.0)

        undamped = SETTINGS.turnKp * (0.7 - 0.5) * 2
        command = controller.update(target(x=0.7), now=0.1)

        self.assertLess(command.turn, undamped)

    def test_reads_settings_from_config_with_defaults(self):
        settings = FollowSettings.fromConfig({"TargetSize": "0.2", "SearchTurn": "0.25"})

        self.assertEqual(settings.targetSize, 0.2)
        self.assertEqual(settings.searchTurn, 0.25)
        self.assertEqual(settings.maxTurn, FollowSettings().maxTurn)


if __name__ == "__main__":
    unittest.main()
