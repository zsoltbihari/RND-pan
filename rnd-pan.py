# MIDI Randomize
# Version: 0.3.93 | Budapest | 2026-09-15 03:23:15 CEST
# Budapest date: 2026-09-15
# Budapest time: 03:23:15
#

import json
from html import escape as html_escape
import math
import random
import sys
import shlex
import shutil
import subprocess
from queue import SimpleQueue
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jack

from PySide6.QtCore import Qt, QSize, QPointF, QTimer, Signal, QEvent
from PySide6.QtGui import QAction, QActionGroup, QContextMenuEvent, QIcon, QPixmap, QPalette, QColor, QFont, QFontMetrics, QTextCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QGroupBox,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QPlainTextEdit,
    QColorDialog,
    QRadioButton,
    QSlider,
    QDial,
)


APP_TITLE = "RND PAN"
DEFAULT_SIZE = 480
DEFAULT_WINDOW_WIDTH = 290
DEFAULT_ACTIVE_STATUS_TEXT = "CH {channel}"
MIN_SIZE = 120
MAX_SIZE = 1920
CHANNEL_COUNT = 16


def midi_note_name(note):
    """Return a conventional MIDI note name, e.g. 69 -> A4."""
    note = max(0, min(127, int(note)))
    names = (
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B",
    )
    return f"{names[note % 12]}{(note // 12) - 1}"


LAYOUTS = {
    "4x4": (4, 4, "4 × 4"),
    "2x8_h": (2, 8, "2 × 8 — horizontal"),
    "2x8_v": (8, 2, "2 × 8 — vertical"),
    "1x16_h": (1, 16, "1 × 16 — horizontal"),
    "1x16_v": (16, 1, "1 × 16 — vertical"),
}
DEFAULT_LAYOUT = "4x4"

LAYOUT_ASPECT_RATIOS = {
    "4x4": 1.0,
    "2x8_h": 4.0,
    "2x8_v": 0.25,
    "1x16_h": 16.0,
    "1x16_v": 1.0 / 16.0,
}

PREFERENCES_FILE = Path("rnd-pan-preferences.json")



def wrapped_tooltip(text, width=340):
    """Return a readable, line-wrapped mouse-over help tooltip."""
    text = "" if text is None else str(text)
    if not text:
        return ""
    return (
        f"<div style='white-space:pre-wrap; width:{int(width)}px;'>"
        f"{html_escape(text).replace(chr(10), '<br>')}"
        "</div>"
    )


def apply_wrapped_tooltips(root, width=340):
    """Apply the same readable wrapping to all existing widget tooltips."""
    widgets = [root]
    widgets.extend(root.findChildren(QWidget))
    for widget in widgets:
        try:
            text = widget.toolTip()
        except RuntimeError:
            continue
        if text and "<div " not in text:
            widget.setToolTip(wrapped_tooltip(text, width))

# ---------------------------------------------------------------------------
# MIDI randomizer
# ---------------------------------------------------------------------------

MIDI_MIN = 0
MIDI_MAX = 127
DEFAULT_RANDOM_MIN = 13
DEFAULT_RANDOM_MAX = 115

# Main-window randomizer graph
GRAPH_MAX_POINTS = 64
DEFAULT_GRAPH_BACKGROUND = "#10181c"
DEFAULT_GRAPH_GRID_COLOR = "#aaff00"
DEFAULT_GRAPH_AXIS_COLOR = "#d5dde2"
DEFAULT_GRAPH_TEXT_COLOR = "#81b0e5"
DEFAULT_GRAPH_POINT_COLOR = "#00e5ff"
DEFAULT_RND_VALUE_COLOR = "#ff0000"
DEFAULT_RND_VALUE_SIZE = 50
DEFAULT_SHOW_CURRENT_RND_VALUE = False
DEFAULT_GRAPH_BEATS = 12
DEFAULT_BUTTON_BACKGROUND_COLOR = "#d9d9d9"
DEFAULT_BUTTON_TEXT_COLOR = "#000000"
DEFAULT_COMBO_BACKGROUND_COLOR = "#4f81bd"
DEFAULT_COMBO_TEXT_COLOR = "#000000"
DEFAULT_WINDOW_TEXT_BACKGROUND_COLOR = "#ffffff"
DEFAULT_WINDOW_TEXT_COLOR = "#7aa6d9"
DEFAULT_POT_VALUE_TEXT_COLOR = "#7aa6d9"
DEFAULT_POT_CAPTION_TEXT_COLOR = "#7aa6d9"
DEFAULT_RANGE_TEXT_COLOR = "#81b0e5"
DEFAULT_ARROW_BACKGROUND_COLOR = "#d9d9d9"
DEFAULT_ARROW_TEXT_COLOR = "#000000"
DEFAULT_DISTRIBUTION_GRAPH_BACKGROUND_COLOR = "#10181c"
DEFAULT_DISTRIBUTION_GRAPH_TEXT_COLOR = "#00e5ff"


COLOR_COLLECTIONS = {
    "Default": {
        "background_color": "#000000",
        "button_background_color": DEFAULT_BUTTON_BACKGROUND_COLOR,
        "button_text_color": DEFAULT_BUTTON_TEXT_COLOR,
        "combo_background_color": DEFAULT_COMBO_BACKGROUND_COLOR,
        "combo_text_color": DEFAULT_COMBO_TEXT_COLOR,
        "graph_background_color": DEFAULT_GRAPH_BACKGROUND,
        "graph_text_color": DEFAULT_GRAPH_TEXT_COLOR,
        "graph_grid_color": DEFAULT_GRAPH_GRID_COLOR,
        "graph_axis_color": DEFAULT_GRAPH_AXIS_COLOR,
        "graph_point_color": DEFAULT_GRAPH_POINT_COLOR,
        "window_text_background_color": DEFAULT_WINDOW_TEXT_BACKGROUND_COLOR,
        "window_text_color": DEFAULT_WINDOW_TEXT_COLOR,
        "pot_value_text_color": DEFAULT_POT_VALUE_TEXT_COLOR,
        "pot_caption_text_color": DEFAULT_POT_CAPTION_TEXT_COLOR,
        "range_text_color": DEFAULT_RANGE_TEXT_COLOR,
        "arrow_background_color": DEFAULT_ARROW_BACKGROUND_COLOR,
        "arrow_text_color": DEFAULT_ARROW_TEXT_COLOR,
        "distribution_graph_background_color": DEFAULT_DISTRIBUTION_GRAPH_BACKGROUND_COLOR,
        "distribution_graph_text_color": DEFAULT_DISTRIBUTION_GRAPH_TEXT_COLOR,
        "rnd_value_color": DEFAULT_RND_VALUE_COLOR,
    },
    "Matrix": {
        "background_color": "#030806", "button_background_color": "#123c25",
        "button_text_color": "#c8ffd7", "combo_background_color": "#092817",
        "combo_text_color": "#baffc9", "graph_background_color": "#020906",
        "graph_text_color": "#8effaa", "graph_grid_color": "#28583a",
        "graph_axis_color": "#d4ffe0", "graph_point_color": "#00ff66",
        "window_text_background_color": "#06190d", "window_text_color": "#a7ffb9",
        "pot_value_text_color": "#d0ffda", "pot_caption_text_color": "#71e995",
        "range_text_color": "#b6ffc8", "arrow_background_color": "#164b2c",
        "arrow_text_color": "#e0ffe8", "distribution_graph_background_color": "#03140a",
        "distribution_graph_text_color": "#00f875", "rnd_value_color": "#f2fff5",
    },
    "Zombie": {
        "background_color": "#10130f", "button_background_color": "#414a35",
        "button_text_color": "#f0f2d5", "combo_background_color": "#252d20",
        "combo_text_color": "#e3edbd", "graph_background_color": "#10150f",
        "graph_text_color": "#c3d49a", "graph_grid_color": "#505d3e",
        "graph_axis_color": "#e0e8c6", "graph_point_color": "#d5e65c",
        "window_text_background_color": "#24291f", "window_text_color": "#e4ebc8",
        "pot_value_text_color": "#f0f2d5", "pot_caption_text_color": "#b8c68c",
        "range_text_color": "#d9e5a6", "arrow_background_color": "#4b563a",
        "arrow_text_color": "#fbffdf", "distribution_graph_background_color": "#171d14",
        "distribution_graph_text_color": "#c7dc76", "rnd_value_color": "#f2f6d8",
    },
    "Vampire": {
        "background_color": "#10070f", "button_background_color": "#4b1830",
        "button_text_color": "#ffe8f0", "combo_background_color": "#28101f",
        "combo_text_color": "#ffd5e2", "graph_background_color": "#100710",
        "graph_text_color": "#e5b4d0", "graph_grid_color": "#67334f",
        "graph_axis_color": "#f6e5ee", "graph_point_color": "#ff315f",
        "window_text_background_color": "#210d1c", "window_text_color": "#ffd7e6",
        "pot_value_text_color": "#ffe9f1", "pot_caption_text_color": "#e5a0c1",
        "range_text_color": "#ffb4cf", "arrow_background_color": "#60213e",
        "arrow_text_color": "#fff0f5", "distribution_graph_background_color": "#190a16",
        "distribution_graph_text_color": "#ff527e", "rnd_value_color": "#fff0f5",
    },
    "Barbie": {
        "background_color": "#fff0f8", "button_background_color": "#e83e9b",
        "button_text_color": "#ffffff", "combo_background_color": "#ffd0e9",
        "combo_text_color": "#641044", "graph_background_color": "#fff7fb",
        "graph_text_color": "#8c1a61", "graph_grid_color": "#ef9bc9",
        "graph_axis_color": "#511037", "graph_point_color": "#ff168d",
        "window_text_background_color": "#ffe0f0", "window_text_color": "#641044",
        "pot_value_text_color": "#641044", "pot_caption_text_color": "#a51c6b",
        "range_text_color": "#851456", "arrow_background_color": "#ff8bc9",
        "arrow_text_color": "#511037", "distribution_graph_background_color": "#fff0f8",
        "distribution_graph_text_color": "#d51b80", "rnd_value_color": "#8c1a61",
    },
}

class MidiRandomizer:
    """Configurable MIDI random-value generator for 7-bit parameters."""

    DISTRIBUTIONS = (
        ("uniform", "UNIF."),
        ("center", "CTR-BIAS"),
        ("edge", "EDGE-BIAS"),
        ("gaussian", "GAUSS."),
    )

    def __init__(
        self,
        minimum=DEFAULT_RANDOM_MIN,
        maximum=DEFAULT_RANDOM_MAX,
        distribution="center",
        bias=0,
        max_change=100,
        prevent_duplicates=True,
        avoid_recent=False,
        recent_history=5,
        interval_ms=500,
    ):
        self.minimum = MIDI_MIN
        self.maximum = MIDI_MAX
        self.distribution = distribution
        self.bias = int(bias)
        self.max_change = int(max_change)
        self.prevent_duplicates = bool(prevent_duplicates)
        self.avoid_recent = bool(avoid_recent)
        self.recent_history = int(recent_history)
        self.interval_ms = max(300, min(3000, int(interval_ms)))
        self.humanize = 0
        self._last_value = None
        self._history = []
        self.set_range(minimum, maximum)
        self.set_distribution(distribution)
        self.set_bias(bias)
        self.set_max_change(max_change)
        self.set_recent_history(recent_history)

    def set_range(self, minimum, maximum):
        minimum = int(minimum)
        maximum = int(maximum)

        if not MIDI_MIN <= minimum <= MIDI_MAX:
            raise ValueError("Minimum must be between 0 and 127.")
        if not MIDI_MIN <= maximum <= MIDI_MAX:
            raise ValueError("Maximum must be between 0 and 127.")
        if minimum > maximum:
            raise ValueError("Minimum cannot be greater than maximum.")

        self.minimum = minimum
        self.maximum = maximum
        # Runtime range is what the main-window Speed control transforms.
        # Preferences Minimum/Maximum remain the base interval.
        self._runtime_minimum = minimum
        self._runtime_maximum = maximum
        self._history = [
            value for value in self._history
            if self.minimum <= value <= self.maximum
        ]

        if self._last_value is not None and not (
            self.minimum <= self._last_value <= self.maximum
        ):
            self._last_value = None

    def set_runtime_range(self, minimum, maximum):
        minimum = max(MIDI_MIN, min(MIDI_MAX, int(minimum)))
        maximum = max(MIDI_MIN, min(MIDI_MAX, int(maximum)))
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        self._runtime_minimum = minimum
        self._runtime_maximum = maximum

    @property
    def runtime_range(self):
        return self._runtime_minimum, self._runtime_maximum

    def set_distribution(self, distribution):
        valid = {key for key, _label in self.DISTRIBUTIONS}
        if distribution not in valid:
            distribution = "uniform"
        self.distribution = distribution

    def set_bias(self, bias):
        self.bias = max(-100, min(100, int(bias)))

    def set_max_change(self, value):
        self.max_change = max(0, min(MIDI_MAX, int(value)))

    def set_interval(self, value):
        self.interval_ms = max(300, min(3000, int(value)))

    def set_humanize(self, value):
        self.humanize = max(0, min(64, int(value)))

    def set_prevent_duplicates(self, enabled):
        self.prevent_duplicates = bool(enabled)

    def set_avoid_recent(self, enabled, history=None):
        self.avoid_recent = bool(enabled)
        if history is not None:
            self.set_recent_history(history)

    def set_recent_history(self, history):
        self.recent_history = max(1, min(32, int(history)))
        self._history = self._history[-self.recent_history:]

    def reset_history(self):
        self._last_value = None
        self._history.clear()

    def _biased_uniform(self):
        u = random.random()
        strength = abs(self.bias) / 100.0
        if strength == 0:
            return u

        exponent = 1.0 + 7.0 * strength
        if self.bias < 0:
            return u ** exponent
        return 1.0 - ((1.0 - u) ** exponent)

    def _candidate(self):
        lo = self._runtime_minimum
        hi = self._runtime_maximum

        if lo == hi:
            return lo

        span = hi - lo
        biased_center = (lo + hi) / 2.0 + (self.bias / 100.0) * span / 2.0
        biased_center = max(lo, min(hi, biased_center))

        if self.distribution == "center":
            value = random.triangular(lo, hi, biased_center)

        elif self.distribution == "edge":
            # Beta(0.5, 0.5) gives a U-shaped distribution, favouring
            # both ends of the selected interval.
            u = random.betavariate(0.5, 0.5)
            if self.bias:
                target = 0.0 if self.bias < 0 else 1.0
                strength = abs(self.bias) / 100.0
                u = u * (1.0 - strength) + target * strength
            value = lo + u * span

        elif self.distribution == "gaussian":
            sigma = max(span / 6.0, 0.35)
            value = random.gauss(biased_center, sigma)

        else:
            value = lo + self._biased_uniform() * span

        return max(lo, min(hi, int(round(value))))

    def generate(self):
        if self._runtime_minimum == self._runtime_maximum:
            value = self._runtime_minimum
            self._last_value = value
            self._history.append(value)
            self._history = self._history[-self.recent_history:]
            return value

        allowed_recent = set(
            self._history[-self.recent_history:]
            if self.avoid_recent
            else []
        )

        lower = self._runtime_minimum
        upper = self._runtime_maximum

        if (
            self._last_value is not None
            and self.max_change < MIDI_MAX
            and lower <= self._last_value <= upper
        ):
            lower = max(lower, self._last_value - self.max_change)
            upper = min(upper, self._last_value + self.max_change)

        candidates = list(range(lower, upper + 1))

        # If the recent-value exclusion would leave no possible value,
        # progressively relax it rather than blocking the generator.
        filtered = [
            value for value in candidates
            if value not in allowed_recent
        ]

        if self.prevent_duplicates and self._last_value is not None:
            filtered = [
                value for value in filtered
                if value != self._last_value
            ]

        if filtered:
            # Generate according to the selected distribution until the
            # result is legal; fall back to the legal set after bounded tries.
            for _ in range(80):
                value = self._candidate()
                if value in filtered:
                    break
            else:
                value = random.choice(filtered)
        else:
            if self.prevent_duplicates and self._last_value is not None:
                non_duplicate = [
                    value for value in candidates
                    if value != self._last_value
                ]
                value = random.choice(non_duplicate) if non_duplicate else self._last_value
            else:
                value = random.choice(candidates)

        self._last_value = value
        self._history.append(value)
        self._history = self._history[-self.recent_history:]
        return value

    @property
    def range(self):
        return self.minimum, self.maximum

    @property
    def last_value(self):
        return self._last_value


randomizer = MidiRandomizer()


IMAGE_ON = Path("images") / "indicator_midi_on.png"
IMAGE_OFF = Path("images") / "indicator_midi_off.png"


class JackMidiBackend:
    """Own the MIDI Patchbay JACK client and its two MIDI ports."""

    def __init__(self, debug_to_terminal=False):
        self.client = None
        self.debug_to_terminal = bool(debug_to_terminal)
        self.midi_in = None
        self.midi_out = None

        # MIDI is always passed through unchanged.
        self.recommended_activity_filter = {
            "Note On": True,
            "Note Off": True,
            "Control Change (CC)": True,
            "Program Change": True,
            "Aftertouch / Channel Pressure": True,
            "Polyphonic Aftertouch": True,
            "System Exclusive (SysEx)": True,
            "MIDI Clock": False,
            "Start": True,
            "Continue": False,
            "Stop": True,
            "Active Sensing": False,
            "System Reset": False,
            "Time Code / MTC": False,
        }
        self.activity_filter = dict(
            self.recommended_activity_filter
        )
        self._activity_counts = [0] * CHANNEL_COUNT

    def start(self):
        if self.client is not None:
            return

        self.client = jack.Client(
            "rnd-pan",
            no_start_server=True,
        )

        self.midi_in = self.client.midi_inports.register(
            "MIDI IN"
        )
        self.midi_out = self.client.midi_outports.register(
            "MIDI OUT"
        )

        # Transparent MIDI pass-through for the prototype.
        self.client.set_process_callback(self.process)
        self.client.activate()

        self.debug_log(
            "JACK MIDI client started: "
            f"{self.midi_in.name} -> {self.midi_out.name}"
        )

    def debug_log(self, message):
        if self.debug_to_terminal:
            timestamp = datetime.now(
                ZoneInfo("Europe/Budapest")
            ).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {message}")

    def set_debug_to_terminal(self, enabled):
        self.debug_to_terminal = bool(enabled)

    def process(self, frames):
        """Filter MIDI events, forward allowed events unchanged, and count them."""
        if self.midi_in is None or self.midi_out is None:
            return

        self.midi_out.clear_buffer()

        for offset, event in self.midi_in.incoming_midi_events():
            event_bytes = bytes(event)

            # The Activity Filter is the real MIDI forwarding filter.
            # Checked types are forwarded unchanged; unchecked types
            # are blocked before MIDI OUT.
            # Activity filters affect only the indicators/UI. Never block
            # MIDI forwarding here (especially Note Off and transport events).
            self.midi_out.write_midi_event(
                offset,
                event_bytes,
            )

            # The indicators react only to MIDI that passed the filter.
            # Channel Voice messages carry a zero-based MIDI channel in
            # the low nibble of the status byte.
            if self.filter_allows_event(event_bytes) and 0x80 <= event_bytes[0] <= 0xEF:
                channel = event_bytes[0] & 0x0F
                self._activity_counts[channel] += 1

    def classify_midi_event(self, event):
        data = bytes(event)
        if not data:
            return None

        status = data[0]

        if 0x80 <= status <= 0xEF:
            return {
                0x80: "Note Off",
                0x90: "Note On",
                0xA0: "Polyphonic Aftertouch",
                0xB0: "Control Change (CC)",
                0xC0: "Program Change",
                0xD0: "Aftertouch / Channel Pressure",
                }.get(status & 0xF0)

        return {
            0xF0: "System Exclusive (SysEx)",
            0xF1: "Time Code / MTC",
            0xF2: "Time Code / MTC",
            0xF3: "Time Code / MTC",
            0xF8: "MIDI Clock",
            0xFA: "Start",
            0xFB: "Continue",
            0xFC: "Stop",
            0xFE: "Active Sensing",
            0xFF: "System Reset",
        }.get(status)

    def filter_allows_event(self, event):
        category = self.classify_midi_event(event)
        return (
            category is not None
            and self.activity_filter.get(category, False)
        )

    def take_channel_activity(self):
        counts = self._activity_counts[:]
        self._activity_counts = [0] * CHANNEL_COUNT
        return counts

    def stop(self):
        if self.client is None:
            return

        try:
            self.client.deactivate()
        finally:
            self.client.close()

        self.midi_in = None
        self.midi_out = None
        self.client = None

        self.debug_log("JACK MIDI client stopped.")

    def available_ports(self, direction):
        """
        Return live MIDI ports from the JACK/PipeWire graph.

        input:
            external MIDI output/source ports that can feed MIDI IN.

        output:
            external MIDI input/destination ports that can receive MIDI OUT.
        """
        if self.client is None:
            return []

        try:
            if direction == "input":
                ports = self.client.get_ports(
                    is_midi=True,
                    is_output=True,
                )
                own_port = self.midi_in
            else:
                ports = self.client.get_ports(
                    is_midi=True,
                    is_input=True,
                )
                own_port = self.midi_out

            own_name = (
                own_port.name
                if own_port is not None
                else ""
            )

            return [
                port
                for port in ports
                if port.name != own_name
                and not port.name.startswith(
                    "midi-randomize:"
                )
            ]
        except Exception:
            return []

    def connected_names(self, port):
        """Return names of ports currently connected to a local port."""
        if port is None or self.client is None:
            return set()

        try:
            return {
                connected.name
                for connected in self.client.get_all_connections(
                    port
                )
            }
        except Exception:
            return set()

    def connect_input(self, external_name):
        """Connect external MIDI source -> Patchbay MIDI IN."""
        if (
            self.client is None
            or self.midi_in is None
            or not external_name
        ):
            return False

        try:
            self.client.connect(
                external_name,
                self.midi_in.name,
            )
            return True
        except Exception as exc:
            self.debug_log(
                f"JACK MIDI input connect failed: {exc}"
            )
            return False

    def disconnect_input(self, external_name):
        """Disconnect external MIDI source -> Patchbay MIDI IN."""
        if (
            self.client is None
            or self.midi_in is None
            or not external_name
        ):
            return False

        try:
            self.client.disconnect(
                external_name,
                self.midi_in.name,
            )
            return True
        except Exception as exc:
            self.debug_log(
                f"JACK MIDI input disconnect failed: {exc}"
            )
            return False

    def connect_output(self, external_name):
        """Connect Patchbay MIDI OUT -> external MIDI destination."""
        if (
            self.client is None
            or self.midi_out is None
            or not external_name
        ):
            return False

        try:
            self.client.connect(
                self.midi_out.name,
                external_name,
            )
            return True
        except Exception as exc:
            self.debug_log(
                f"JACK MIDI output connect failed: {exc}"
            )
            return False

    def disconnect_output(self, external_name):
        """Disconnect Patchbay MIDI OUT -> external destination."""
        if (
            self.client is None
            or self.midi_out is None
            or not external_name
        ):
            return False

        try:
            self.client.disconnect(
                self.midi_out.name,
                external_name,
            )
            return True
        except Exception as exc:
            self.debug_log(
                f"JACK MIDI output disconnect failed: {exc}"
            )
            return False


class RndPanBackend(JackMidiBackend):
    """MIDI Randomize backend variant: Note On triggers randomized CC10 Pan."""

    def __init__(self, debug_to_terminal=False):
        super().__init__(debug_to_terminal=debug_to_terminal)
        self.randomization_enabled = False
        self.current_pan = [64] * CHANNEL_COUNT
        self._generated_values = SimpleQueue()
        self.log_callback = None
        self.debug_event_logging = True

    def set_randomization_enabled(self, enabled):
        self.randomization_enabled = bool(enabled)

    def take_generated_values(self):
        values = []
        while True:
            try:
                values.append(self._generated_values.get_nowait())
            except Exception:
                break
        return values

    def _log_note_value(self, message):
        # JACK callbacks must not perform file I/O or update Qt widgets.
        # Queue the message for the GUI thread; terminal/file output happens there.
        callback = getattr(self, "log_callback", None)
        if callback is not None and self.debug_event_logging:
            callback(message)
        elif self.debug_to_terminal:
            timestamp = datetime.now(ZoneInfo("Europe/Budapest")).strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] {message}", flush=True)

    def process(self, frames):
        if self.midi_in is None or self.midi_out is None:
            return

        self.midi_out.clear_buffer()

        for offset, event in self.midi_in.incoming_midi_events():
            event_bytes = bytes(event)
            if not event_bytes:
                continue

            # Display/activity filters must never suppress outgoing MIDI.
            status = event_bytes[0]
            channel = status & 0x0F

            # Track incoming CC10 so the terminal can show the Pan value
            # that was present when the Note On arrived.
            if (
                len(event_bytes) >= 3
                and (status & 0xF0) == 0xB0
                and event_bytes[1] == 10
            ):
                self.current_pan[channel] = event_bytes[2]
                self.midi_out.write_midi_event(offset, event_bytes)
                if self.filter_allows_event(event_bytes) and 0x80 <= status <= 0xEF:
                    self._activity_counts[channel] += 1
                continue

            if (
                self.randomization_enabled
                and len(event_bytes) >= 3
                and (status & 0xF0) == 0x90
                and event_bytes[2] != 0
            ):
                note = event_bytes[1]
                incoming_pan = self.current_pan[channel]
                if randomizer.humanize > 0:
                    deviation = random.randint(
                        -randomizer.humanize,
                        randomizer.humanize,
                    )
                    outgoing_pan = max(
                        MIDI_MIN,
                        min(MIDI_MAX, incoming_pan + deviation),
                    )
                else:
                    outgoing_pan = randomizer.generate()

                # Send PAN first at the same JACK offset so the receiving
                # instrument can apply it to the note that follows.
                pan_event = bytes((0xB0 | channel, 10, outgoing_pan))
                self.midi_out.write_midi_event(offset, pan_event)
                self.midi_out.write_midi_event(offset, event_bytes)

                self.current_pan[channel] = outgoing_pan
                self._generated_values.put(outgoing_pan)

                self._log_note_value(
                    f"CH {channel + 1}  {midi_note_name(note)}  PAN {incoming_pan} → {outgoing_pan}"
                )

                if self.filter_allows_event(event_bytes):
                    self._activity_counts[channel] += 1
                continue

            self.midi_out.write_midi_event(offset, event_bytes)

            if self.filter_allows_event(event_bytes) and 0x80 <= status <= 0xEF:
                self._activity_counts[channel] += 1


class MidiPortPage(QWidget):
    """Live JACK/PipeWire MIDI Input or MIDI Output settings page."""

    def __init__(self, parent_dialog, direction):
        super().__init__(parent_dialog)

        self.parent_dialog = parent_dialog
        self.direction = direction

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(7)

        title = (
            "MIDI Input"
            if direction == "input"
            else "MIDI Output"
        )
        layout.addWidget(
            parent_dialog.page_title(title)
        )

        if direction == "input":
            description_text = (
                "Select the JACK/PipeWire MIDI source that should "
                "feed the filter. The list is refreshed continuously "
                "while the settings dialog is open, so newly available "
                "or disconnected MIDI sources are reflected automatically."
            )
            list_title = "Available MIDI input sources"
        else:
            description_text = (
                "Select the JACK/PipeWire MIDI destination that should "
                "receive data from the filter. The list is refreshed "
                "continuously while the settings dialog is open, so newly "
                "available or disconnected MIDI destinations are reflected "
                "automatically."
            )
            list_title = "Available MIDI output destinations"

        description = QLabel(description_text)
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #000000; font-size: 12px;"
        )
        layout.addWidget(description)

        self.port_list = QListWidget()
        self.port_list.setStyleSheet(
            "QListWidget {"
            "font-size: 13px;"
            "padding: 2px;"
            "}"
            "QListWidget::item {"
            "min-height: 21px;"
            "padding: 2px 4px;"
            "}"
        )
        self.port_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.port_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.port_list.customContextMenuRequested.connect(
            self.show_context_menu
        )
        self.port_list.setMinimumHeight(145)

        group = QGroupBoxCompat(list_title)
        group_layout = group.layout()
        group_layout.addWidget(self.port_list)
        layout.addWidget(group)

        actions = QHBoxLayout()

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(
            self.connect_selected
        )

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(
            self.disconnect_selected
        )

        actions.addWidget(self.connect_button)
        actions.addWidget(self.disconnect_button)
        actions.addStretch()

        layout.addLayout(actions)

        self.status_label = QLabel(
            "JACK/PipeWire: waiting for MIDI port information"
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #9dcbff; font-size: 11px;"
        )
        layout.addWidget(self.status_label)
        layout.addStretch()

        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.addStretch()
        help_button = QPushButton("?")
        help_button.setMaximumWidth(28)
        help_button.clicked.connect(self.show_local_help)
        help_button.setToolTip("Local help")
        help_row.addWidget(help_button)
        layout.addLayout(help_row)

        self.refresh()

    def show_local_help(self):
        if self.direction == "input":
            title = "MIDI Input Help"
            message = (
                "MIDI Input\n\n"
                "Select the JACK/PipeWire MIDI source from which "
                "the processor receives incoming MIDI events."
            )
        else:
            title = "MIDI Output Help"
            message = (
                "MIDI Output\n\n"
                "Select the JACK/PipeWire MIDI destination that receives "
                "the processed MIDI events."
            )
        QMessageBox.information(self, title, message)

    def selected_port_name(self):
        item = self.port_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def refresh(self):
        backend = self.parent_dialog.backend

        # Remember both the selected port and the exact scroll position.
        # Rebuilding a QListWidget normally resets the scrollbar to the top,
        # which is especially annoying while browsing long JACK port lists.
        previous = self.selected_port_name()
        scroll_value = self.port_list.verticalScrollBar().value()

        if self.direction == "input":
            ports = backend.available_ports("input")
            connected = backend.connected_names(
                backend.midi_in
            )
        else:
            ports = backend.available_ports("output")
            connected = backend.connected_names(
                backend.midi_out
            )

        self.port_list.blockSignals(True)
        self.port_list.setUpdatesEnabled(False)
        self.port_list.clear()

        selected_row = -1
        connected_row = -1

        for row, port in enumerate(ports):
            is_connected = port.name in connected

            # Use the same radio-button style as the reference
            # Preferences panel: filled circle = connected,
            # empty circle = not connected.
            marker = (
                "● "
                if is_connected
                else "○ "
            )

            item = QListWidgetItem(
                marker + port.name
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                port.name,
            )

            if is_connected:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            self.port_list.addItem(item)

            if port.name == previous:
                selected_row = row

            if connected_row < 0 and port.name in connected:
                connected_row = row

        # Restore the user's selection. If the selected port disappeared,
        # fall back to the first connected port, as before.
        if selected_row >= 0:
            self.port_list.setCurrentRow(
                selected_row
            )
        elif connected_row >= 0:
            self.port_list.setCurrentRow(
                connected_row
            )
        else:
            self.port_list.clearSelection()

        self.port_list.setUpdatesEnabled(True)

        # Restore the exact vertical position after rebuilding the list.
        scrollbar = self.port_list.verticalScrollBar()
        scrollbar.setValue(
            min(
                scroll_value,
                scrollbar.maximum(),
            )
        )

        self.update_buttons()

    def update_buttons(self):
        selected = self.selected_port_name()

        if self.direction == "input":
            connected = self.parent_dialog.backend.connected_names(
                self.parent_dialog.backend.midi_in
            )
        else:
            connected = self.parent_dialog.backend.connected_names(
                self.parent_dialog.backend.midi_out
            )

        self.connect_button.setEnabled(
            selected is not None
            and selected not in connected
        )
        self.disconnect_button.setEnabled(
            selected is not None
            and selected in connected
        )

    def connect_selected(self):
        name = self.selected_port_name()
        if not name:
            return

        if self.direction == "input":
            ok = self.parent_dialog.backend.connect_input(name)
        else:
            ok = self.parent_dialog.backend.connect_output(name)

        if not ok:
            QMessageBox.warning(
                self,
                "JACK connection",
                "Could not connect the selected MIDI port.\n\n"
                f"{name}",
            )

        self.refresh()

    def disconnect_selected(self):
        name = self.selected_port_name()
        if not name:
            return

        if self.direction == "input":
            ok = self.parent_dialog.backend.disconnect_input(name)
        else:
            ok = self.parent_dialog.backend.disconnect_output(name)

        if not ok:
            QMessageBox.warning(
                self,
                "JACK connection",
                "Could not disconnect the selected MIDI port.\n\n"
                f"{name}",
            )

        self.refresh()

    def show_context_menu(self, position):
        """Show a reliable Connect/Disconnect menu for the right-clicked port."""
        item = self.port_list.itemAt(position)
        if item is None:
            return

        # Right-click also selects the row, so the visual state follows
        # exactly the port on which the user opened the menu.
        self.port_list.setCurrentItem(item)

        name = item.data(
            Qt.ItemDataRole.UserRole
        )
        if not name:
            return

        backend = self.parent_dialog.backend

        if self.direction == "input":
            connected = backend.connected_names(
                backend.midi_in
            )
        else:
            connected = backend.connected_names(
                backend.midi_out
            )

        is_connected = name in connected

        menu = QMenu(self.port_list)
        connect_action = menu.addAction("Connect")
        disconnect_action = menu.addAction("Disconnect")

        connect_action.setEnabled(
            not is_connected
        )
        disconnect_action.setEnabled(
            is_connected
        )

        # Connect the QAction directly to methods which receive the
        # exact port name captured at the moment of the right-click.
        connect_action.triggered.connect(
            lambda checked=False, port_name=name:
                self.connect_port_by_name(port_name)
        )
        disconnect_action.triggered.connect(
            lambda checked=False, port_name=name:
                self.disconnect_port_by_name(port_name)
        )

        menu.exec(
            self.port_list.viewport().mapToGlobal(
                position
            )
        )

    def connect_port_by_name(self, name):
        """Connect one explicitly named JACK MIDI port."""
        backend = self.parent_dialog.backend

        if self.direction == "input":
            ok = backend.connect_input(name)
        else:
            ok = backend.connect_output(name)

        if not ok:
            QMessageBox.warning(
                self,
                "JACK connection",
                "Could not connect the selected MIDI port.\n\n"
                f"{name}",
            )

        self.refresh()

    def disconnect_port_by_name(self, name):
        """Disconnect one explicitly named JACK MIDI port."""
        backend = self.parent_dialog.backend

        if self.direction == "input":
            ok = backend.disconnect_input(name)
        else:
            ok = backend.disconnect_output(name)

        if not ok:
            QMessageBox.warning(
                self,
                "JACK connection",
                "Could not disconnect the selected MIDI port.\n\n"
                f"{name}",
            )

        self.refresh()


class QGroupBoxCompat(QGroupBox):
    """Compact framed section matching the reference settings panel."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)

        self.inner = QVBoxLayout()
        self.inner.setContentsMargins(
            6, 6, 6, 6
        )
        self.inner.setSpacing(4)
        super().setLayout(self.inner)

    def layout(self):
        return self.inner


class LayoutsPage(QWidget):
    """Visibility controls for the main PAN-randomizer window."""

    def __init__(
        self,
        main_window=None,
        show_graph=True,
        show_controls=True,
        show_interval=True,
        start_in_play=False,
        parent=None,
    ):
        super().__init__(parent)
        self.main_window = main_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        title = QLabel("Layouts")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "Choose which elements are visible in the main window. "
            "Changes are applied immediately and saved automatically."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.graph_checkbox = QCheckBox("Show Graph")
        self.graph_checkbox.setChecked(bool(show_graph))
        self.graph_checkbox.toggled.connect(
            lambda checked: self._set_visibility("graph", checked)
        )
        layout.addWidget(self.graph_checkbox)

        self.controls_checkbox = QCheckBox(
            "Show Knobs and Distribution (including values)"
        )
        self.controls_checkbox.setChecked(bool(show_controls))
        self.controls_checkbox.toggled.connect(
            lambda checked: self._set_visibility("controls", checked)
        )
        layout.addWidget(self.controls_checkbox)

        self.interval_checkbox = QCheckBox("Show Interval")
        self.interval_checkbox.setChecked(bool(show_interval))
        self.interval_checkbox.toggled.connect(
            lambda checked: self._set_visibility("interval", checked)
        )
        layout.addWidget(self.interval_checkbox)

        self.start_in_play_checkbox = QCheckBox("Start in PLAY mode")
        self.start_in_play_checkbox.setChecked(bool(start_in_play))
        self.start_in_play_checkbox.setToolTip(
            "When enabled, start PAN randomization automatically at launch."
        )
        self.start_in_play_checkbox.toggled.connect(self._set_start_in_play)
        layout.addWidget(self.start_in_play_checkbox)
        layout.addStretch(1)

    def _set_visibility(self, element, visible):
        if self.main_window is not None:
            self.main_window.set_main_element_visibility(element, visible)

    def _set_start_in_play(self, enabled):
        if self.main_window is not None:
            self.main_window.set_start_in_play(enabled)

    def sync_from_main(self, layout_mode=None, resizable=None):
        if self.main_window is None:
            return
        values = (
            (self.graph_checkbox, self.main_window.show_graph),
            (self.controls_checkbox, self.main_window.show_controls),
            (self.interval_checkbox, self.main_window.show_interval),
            (self.start_in_play_checkbox, self.main_window.start_in_play),
        )
        for checkbox, value in values:
            checkbox.blockSignals(True)
            try:
                checkbox.setChecked(bool(value))
            finally:
                checkbox.blockSignals(False)

    def value(self):
        return self.main_window.window_size if self.main_window is not None else DEFAULT_SIZE

    def resizable(self):
        return bool(self.main_window.window_resizable) if self.main_window is not None else True

    def layout_mode(self):
        return self.main_window.layout_mode if self.main_window is not None else DEFAULT_LAYOUT


class WindowSizePage(QWidget):
    """Square window-size settings page."""

    def __init__(
        self,
        current_size,
        default_size,
        resizable,
        parent=None,
    ):
        super().__init__(parent)

        self.default_size = default_size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        title = QLabel("Window Size")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )

        description = QLabel(
            f"Set the square MIDI indicator window size. "
            f"Allowed range: {MIN_SIZE}–{MAX_SIZE} pixels. "
            "Width and height are always identical."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #000000; font-size: 12px;"
        )

        size_row = QHBoxLayout()
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.setSpacing(6)

        size_row.addWidget(
            QLabel("Size:")
        )

        self.size_spin = QSpinBox()
        self.size_spin.setRange(
            MIN_SIZE,
            MAX_SIZE,
        )
        self.size_spin.setValue(
            max(
                MIN_SIZE,
                min(
                    MAX_SIZE,
                    int(current_size),
                ),
            )
        )
        self.size_spin.setSuffix(" px")
        self.size_spin.setMaximumWidth(120)
        size_row.addWidget(self.size_spin)
        size_row.addStretch()

        self.resize_checkbox = QCheckBox(
            "Allow mouse resizing"
        )
        self.resize_checkbox.setChecked(
            bool(resizable)
        )

        reset = QPushButton(
            "Reset to default"
        )
        reset.setMaximumWidth(150)
        reset.clicked.connect(
            self.reset_default
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(5)
        layout.addLayout(size_row)
        layout.addWidget(
            self.resize_checkbox
        )
        layout.addStretch()
        layout.addWidget(reset)

    def reset_default(self):
        self.size_spin.setValue(
            self.default_size
        )

    def value(self):
        return self.size_spin.value()

    def resizable(self):
        return self.resize_checkbox.isChecked()


class MidiFilterPage(QWidget):
    """MIDI message activity filter settings page."""

    TOOLTIP_TEXTS = {
        "Note On": "Allows MIDI Note On messages to pass through the filter.",
        "Note Off": "Allows MIDI Note Off messages to pass through the filter.",
        "Control Change (CC)": "Allows MIDI Control Change (CC) messages to pass through the filter.",
        "Program Change": "Allows MIDI Program Change messages to pass through the filter.",
        "Aftertouch / Channel Pressure": "Allows Channel Pressure (Aftertouch) messages to pass through the filter.",
        "Polyphonic Aftertouch": "Allows Polyphonic Aftertouch messages to pass through the filter.",
        "System Exclusive (SysEx)": "Allows System Exclusive (SysEx) messages to pass through the filter.",
        "MIDI Clock": (
            "Triggers the indicator for MIDI Clock timing messages. "
            "Disabled by default because Clock can arrive continuously."
        ),
        "Start": "Allows MIDI Start messages to pass through the filter.",
        "Continue": "Allows MIDI Continue messages to pass through the filter.",
        "Stop": "Allows MIDI Stop messages to pass through the filter.",
        "Active Sensing": (
            "Triggers the indicator for MIDI Active Sensing messages. "
            "Disabled by default because these may arrive continuously."
        ),
        "System Reset": "Allows MIDI System Reset messages to pass through the filter.",
        "Time Code / MTC": "Allows MIDI Time Code / MTC System Common messages to pass through the filter.",
    }

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.checks = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(7)

        title = QLabel("MIDI Filter")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )

        description = QLabel(
            "Choose which MIDI message types should trigger the activity "
            "indicator. This filter affects only the indication: every MIDI "
            "message is still passed through unchanged."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #000000; font-size: 12px;"
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(5)

        # Only the approved message types are presented in Preferences.
        # Legacy system-message entries are hidden from this page.
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(24)

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(7)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(7)

        categories = [
            "Note On",
            "Note Off",
            "Control Change (CC)",
            "Program Change",
            "Aftertouch / Channel Pressure",
            "Polyphonic Aftertouch",
            "MIDI Clock",
        ]
        split_index = 4

        for column, column_categories in (
            (left_column, categories[:split_index]),
            (right_column, categories[split_index:]),
        ):
            for category in column_categories:
                check = QCheckBox(category)
                check.setChecked(
                    self.backend.activity_filter[category]
                )
                # QCheckBox tooltip covers both the box and its label.
                check.setToolTip(
                    self.TOOLTIP_TEXTS.get(
                        category,
                        "Controls whether this MIDI message type is allowed through the MIDI filter.",
                    )
                )
                check.toggled.connect(
                    lambda checked, name=category:
                    self.set_filter_value(name, checked)
                )
                column.addWidget(check)
                self.checks[category] = check

            column.addStretch()

        columns.addLayout(left_column)
        columns.addLayout(right_column)
        layout.addLayout(columns)

        quick_actions = QHBoxLayout()
        select_all = QPushButton("Select All")
        clear_all = QPushButton("Clear All")
        reset_recommended = QPushButton("Reset to Recommended")

        select_all.setToolTip(
            "Enable all MIDI message types for activity indication."
        )
        clear_all.setToolTip(
            "Disable all MIDI message types for activity indication."
        )
        reset_recommended.setToolTip(
            "Restore the recommended Activity Filter settings."
        )

        select_all.clicked.connect(
            lambda: [
                check.setChecked(True)
                for check in self.checks.values()
            ]
        )
        clear_all.clicked.connect(
            lambda: [
                check.setChecked(False)
                for check in self.checks.values()
            ]
        )
        reset_recommended.clicked.connect(
            self.reset_recommended
        )

        quick_actions.addWidget(select_all)
        quick_actions.addWidget(clear_all)
        quick_actions.addWidget(reset_recommended)
        quick_actions.addStretch()
        help_button = QPushButton("?")
        help_button.setMaximumWidth(28)
        help_button.clicked.connect(self.show_local_help)
        help_button.setToolTip("Local help")
        quick_actions.addWidget(help_button)
        layout.addLayout(quick_actions)
        layout.addStretch()

    def show_local_help(self):
        QMessageBox.information(
            self,
            "MIDI Filter Help",
            "MIDI Filter\n\n"
            "The selected MIDI message types trigger the MIDI activity "
            "indicator. Message forwarding is independent of this filter "
            "and remains unchanged.\n\n"
            "Reset to Recommended restores the recommended filter settings."
        )

    def reset_recommended(self):
        answer = QMessageBox.question(
            self,
            "Reset to Recommended",
            "Reset all MIDI Filter settings to the recommended values?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        for category, check in self.checks.items():
            check.setChecked(
                self.backend.recommended_activity_filter.get(
                    category,
                    False,
                )
            )

    def set_filter_value(self, category, enabled):
        """Apply one filter change immediately to the live backend."""
        self.backend.activity_filter[category] = bool(enabled)

    def sync_filter(self):
        """Synchronize visible checkbox values with the live backend."""
        for category, check in self.checks.items():
            self.backend.activity_filter[category] = check.isChecked()


class MidiMonitorDialog(QDialog):
    """Live ALSA MIDI /proc monitor window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ALSA MIDI Device Status")
        self.resize(368, 483)
        self.setMinimumSize(300, 260)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel("ALSA MIDI device:"))

        self.device_combo = QComboBox()
        self.device_combo.setToolTip(
            "Select the ALSA MIDI /proc entry to monitor."
        )
        top.addWidget(self.device_combo, 1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.refresh_button.setToolTip(
            "Refresh the available ALSA MIDI /proc devices."
        )
        top.addWidget(self.refresh_button)
        root.addLayout(top)

        explanation = QLabel(
            "This window shows the live kernel-facing ALSA MIDI device status "
            "exposed through /proc/asound.\n"
            "It is not a MIDI event monitor: the values are driver counters, "
            "buffer state and ownership information.\n"
            "The selected entry is read every 200 ms, similar to repeated "
            "cat/watch use from a terminal.\n"
            "See Detailed Help for ALSA/kernel-level diagnostics and commands."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #555555;")
        root.addWidget(explanation)

        self.monitor = QPlainTextEdit()
        self.monitor.setReadOnly(True)
        self.monitor.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.monitor.setStyleSheet(
            "font-family: monospace; font-size: 11px;"
        )
        root.addWidget(self.monitor, 1)

        bottom = QHBoxLayout()
        self.status_label = QLabel("Monitoring stopped")
        self.status_label.setStyleSheet("color: #9e9e9e;")
        bottom.addWidget(self.status_label)
        bottom.addStretch()

        help_button = QPushButton("Detailed Help")
        help_button.clicked.connect(self.show_detailed_help)
        help_button.setToolTip(
            "Detailed ALSA /proc diagnostics and terminal commands."
        )
        bottom.addWidget(help_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        bottom.addWidget(close_button)
        root.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_monitor)

        self.refresh_devices()

        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self.move(
                geometry.left()
                + (geometry.width() - self.width()) // 2,
                geometry.top()
                + (geometry.height() - self.height()) // 2,
            )

    def show_detailed_help(self):
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("ALSA MIDI Device Status — Detailed Help")
        help_dialog.resize(517, 422)
        help_dialog.setMinimumSize(422, 326)

        layout = QVBoxLayout(help_dialog)
        help_text = QPlainTextEdit()
        help_text.setReadOnly(True)
        help_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        help_text.setStyleSheet(
            "font-family: monospace; font-size: 11px;"
        )

        details = """ALSA MIDI /proc STATUS — technical reference

This window reads Linux ALSA MIDI status exposed under /proc/asound.
It is a diagnostic view of ALSA driver/device state, not a decoder
of MIDI events.

Typical fields:
  Type         ALSA MIDI device type
  Output/Input MIDI stream instance
  Tx bytes     Number of bytes transmitted
  Rx bytes     Number of bytes received
  Owner PID    Process owning the stream endpoint
  Mode         Current stream mode when exposed by the driver
  Buffer size  Kernel/driver MIDI buffer size
  Avail        Currently available buffer space/data
  Overruns     Detected receive buffer overruns

TERMINAL COMMANDS
=================

List ALSA cards:
  cat /proc/asound/cards

List ALSA directories:
  ls -l /proc/asound/

Find MIDI /proc entries:
  find /proc/asound -maxdepth 2 -type f -name 'midi*' -print

Read one device once:
  cat /proc/asound/card3/midi0

Refresh every 0.2 seconds:
  watch -n 0.2 'cat /proc/asound/card3/midi0 2>/dev/null'

Read every discovered MIDI entry:
  for f in /proc/asound/card*/midi*; do
      echo "=== $f ==="
      cat "$f"
  done

Kernel ALSA information:
  cat /proc/asound/version
  cat /proc/asound/modules

KERNEL-LEVEL NOTES
==================

Rising Rx bytes indicates received data; rising Tx bytes indicates
transmitted data. An increasing Overruns value points to receive-side
buffer pressure or insufficient servicing.

The exact fields depend on the ALSA driver and kernel version.
This application displays the kernel-provided /proc content without
rewriting those values."""
        help_text.setPlainText(details)
        layout.addWidget(help_text, 1)

        close_help = QPushButton("Close")
        close_help.clicked.connect(help_dialog.accept)
        layout.addWidget(close_help)

        help_dialog.exec()

    def find_devices(self):
        devices = []
        proc_root = Path("/proc/asound")
        if not proc_root.exists():
            return devices

        for midi_file in sorted(proc_root.glob("card*/midi*")):
            if midi_file.is_file():
                devices.append(midi_file)

        return devices

    def device_display_name(self, path):
        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return path.name

        first_line = content.splitlines()[0].strip() if content.splitlines() else ""
        return first_line or path.name

    def refresh_devices(self):
        current = self.device_combo.currentData()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()

        devices = self.find_devices()
        for path in devices:
            display_name = self.device_display_name(path)
            self.device_combo.addItem(display_name, str(path))

        self.device_combo.blockSignals(False)

        if current:
            index = self.device_combo.findData(current)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

        if self.device_combo.count() == 0:
            self.monitor.setPlainText(
                "/proc/asound MIDI entries were not found."
            )
            self.status_label.setText("No ALSA MIDI devices found")
            self.timer.stop()
            return

        self.timer.start()
        self.update_monitor()

    def update_monitor(self):
        path = self.device_combo.currentData()
        if not path:
            return

        try:
            content = Path(path).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            self.monitor.setPlainText(
                f"Cannot read {path}\n\n{exc}"
            )
            self.status_label.setText("Read error")
            return

        # Keep the user's current scroll position during the 200 ms refresh.
        # setPlainText() normally resets the view, which is especially annoying
        # for devices with long /proc status output (for example 4i4o devices).
        vertical_scroll = self.monitor.verticalScrollBar().value()
        horizontal_scroll = self.monitor.horizontalScrollBar().value()
        cursor_position = self.monitor.textCursor().position()

        new_content = content.rstrip()
        if self.monitor.toPlainText() != new_content:
            self.monitor.setPlainText(new_content)

            cursor = self.monitor.textCursor()
            cursor.setPosition(
                min(cursor_position, len(new_content))
            )
            self.monitor.setTextCursor(cursor)

            # Restore the exact previous viewport after Qt recalculates
            # the document's scroll range.
            self.monitor.verticalScrollBar().setValue(
                vertical_scroll
            )
            self.monitor.horizontalScrollBar().setValue(
                horizontal_scroll
            )

        self.status_label.setText("Live — refresh 200 ms")

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()


class RangeSlider(QSlider):
    """Horizontal two-handle slider for an inclusive integer range."""

    def __init__(self, minimum=0, maximum=127, low=30, high=97, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)

        self.setRange(minimum, maximum)
        self._low = int(low)
        self._high = int(high)
        self._drag_handle = None
        self.setMinimumHeight(34)

    def low_value(self):
        return self._low

    def high_value(self):
        return self._high

    def set_values(self, low, high):
        low = max(self.minimum(), min(self.maximum(), int(low)))
        high = max(self.minimum(), min(self.maximum(), int(high)))
        if low > high:
            low, high = high, low

        changed = (low != self._low or high != self._high)
        self._low = low
        self._high = high

        if changed:
            self.update()
            self.valuesChanged.emit(self._low, self._high)

    def set_low_value(self, value):
        value = max(self.minimum(), min(self._high, int(value)))
        if value != self._low:
            self._low = value
            self.update()
            self.valuesChanged.emit(self._low, self._high)

    def set_high_value(self, value):
        value = min(self.maximum(), max(self._low, int(value)))
        if value != self._high:
            self._high = value
            self.update()
            self.valuesChanged.emit(self._low, self._high)

    valuesChanged = Signal(int, int)

    def _handle_x(self, value):
        span = self.maximum() - self.minimum()
        if span <= 0:
            return self.rect().left()

        usable = max(1, self.width() - 16)
        return 8 + round(
            (value - self.minimum()) * usable / span
        )

    def _value_at_x(self, x):
        usable = max(1, self.width() - 16)
        ratio = (x - 8) / usable
        ratio = max(0.0, min(1.0, ratio))
        return round(
            self.minimum() + ratio * (self.maximum() - self.minimum())
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        y = self.height() // 2
        left = 8
        right = self.width() - 8

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c8c8c8"))
        painter.drawRoundedRect(
            left,
            y - 3,
            max(1, right - left),
            6,
            3,
            3,
        )

        low_x = self._handle_x(self._low)
        high_x = self._handle_x(self._high)

        painter.setBrush(QColor("#4f81bd"))
        painter.drawRoundedRect(
            low_x,
            y - 3,
            max(1, high_x - low_x),
            6,
            3,
            3,
        )

        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QColor("#555555"))
        painter.drawEllipse(low_x - 7, y - 7, 14, 14)
        painter.drawEllipse(high_x - 7, y - 7, 14, 14)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x = event.position().x()
        low_x = self._handle_x(self._low)
        high_x = self._handle_x(self._high)

        if abs(x - low_x) <= abs(x - high_x):
            self._drag_handle = "low"
        else:
            self._drag_handle = "high"

        self._set_from_mouse(x)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_handle is not None:
            self._set_from_mouse(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_handle = None
        event.accept()

    def _set_from_mouse(self, x):
        value = self._value_at_x(x)
        if self._drag_handle == "low":
            self.set_low_value(value)
        elif self._drag_handle == "high":
            self.set_high_value(value)



class MainRangeIndicator(QWidget):
    """Interactive 0–127 range control used by the main window."""

    rangeChanged = Signal(int, int)

    def __init__(self, low=0, high=127, parent=None):
        super().__init__(parent)
        self._low = int(low)
        self._high = int(high)
        self._text_color = QColor("#555555")
        self._drag_handle = None
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_values(self, low, high):
        low = max(MIDI_MIN, min(MIDI_MAX, int(low)))
        high = max(MIDI_MIN, min(MIDI_MAX, int(high)))
        if low > high:
            low, high = high, low
        changed = low != self._low or high != self._high
        self._low, self._high = low, high
        if changed:
            self.update()

    def set_text_color(self, color):
        self._text_color = QColor(color)
        self.update()

    def _handle_x(self, value):
        usable = max(1, self.width() - 20)
        return 10 + round((value - MIDI_MIN) * usable / MIDI_MAX)

    def _value_from_x(self, x):
        left, right = 10, max(11, self.width() - 10)
        x = max(left, min(right, int(x)))
        return max(MIDI_MIN, min(MIDI_MAX, round((x-left) * MIDI_MAX / (right-left))))

    def _nearest_handle(self, x):
        lx, hx = self._handle_x(self._low), self._handle_x(self._high)
        return "low" if abs(x-lx) <= abs(x-hx) else "high"

    def _set_from_mouse(self, x):
        value = self._value_from_x(x)
        if self._drag_handle == "low":
            value = min(value, self._high)
            if value != self._low:
                self._low = value
                self.rangeChanged.emit(self._low, self._high)
                self.update()
        elif self._drag_handle == "high":
            value = max(value, self._low)
            if value != self._high:
                self._high = value
                self.rangeChanged.emit(self._low, self._high)
                self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_handle = self._nearest_handle(event.position().x())
            self._set_from_mouse(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_handle is not None:
            self._set_from_mouse(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_handle = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, track_y = 10, max(11, self.width()-10), 13

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c8c8c8"))
        painter.drawRoundedRect(left, track_y-3, right-left, 6, 3, 3)

        low_x, high_x = self._handle_x(self._low), self._handle_x(self._high)
        painter.setBrush(QColor("#4f81bd"))
        painter.drawRoundedRect(low_x, track_y-3, max(1, high_x-low_x), 6, 3, 3)

        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QColor("#555555"))
        painter.drawEllipse(low_x-7, track_y-7, 14, 14)
        painter.drawEllipse(high_x-7, track_y-7, 14, 14)

        font = painter.font()
        font.setPointSize(max(7, font.pointSize()-1))
        painter.setFont(font)
        painter.setPen(self._text_color)
        fm = QFontMetrics(font)
        lo_text, hi_text = str(self._low), str(self._high)
        lo_w, hi_w = fm.horizontalAdvance(lo_text), fm.horizontalAdvance(hi_text)
        lo_x, hi_x = low_x-lo_w//2, high_x-hi_w//2
        if hi_x < lo_x+lo_w+3:
            lo_x = max(left, low_x-lo_w-4)
            hi_x = min(right-hi_w, high_x+4)
        lo_x = max(left, min(right-lo_w, lo_x))
        hi_x = max(left, min(right-hi_w, hi_x))
        painter.drawText(lo_x, 26, lo_w, 12, Qt.AlignmentFlag.AlignCenter, lo_text)
        painter.drawText(hi_x, 26, hi_w, 12, Qt.AlignmentFlag.AlignCenter, hi_text)


class DistributionPreview(QWidget):
    """Compact visual preview of the selected random distribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.distribution = "uniform"
        self.bias = 0
        self.background_color = DEFAULT_DISTRIBUTION_GRAPH_BACKGROUND_COLOR
        self.text_color = DEFAULT_DISTRIBUTION_GRAPH_TEXT_COLOR
        self.setMinimumHeight(88)
        self.setMaximumHeight(105)

    def set_colors(self, background=None, text=None):
        for value, attr in (
            (background, "background_color"),
            (text, "text_color"),
        ):
            if value is not None:
                color = QColor(value)
                if color.isValid():
                    setattr(self, attr, color.name())
        self.update()

    def set_distribution(self, distribution):
        self.distribution = distribution
        self.update()

    def set_bias(self, bias):
        self.bias = int(bias)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.setPen(QColor(self.text_color))
        painter.setBrush(QColor(self.background_color))
        painter.drawRoundedRect(rect, 4, 4)

        plot = rect.adjusted(12, 10, -12, -14)
        painter.setPen(QColor(self.text_color))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())

        points = []
        count = 80
        strength = abs(self.bias) / 100.0

        for i in range(count + 1):
            x = i / count
            if self.distribution == "center":
                center = 0.5 + (self.bias / 100.0) * 0.5
                sigma = 0.16
                y = pow(2.718281828, -((x - center) ** 2) / (2 * sigma ** 2))
            elif self.distribution == "edge":
                y = 1.0 / max(0.12, ((x * (1.0 - x)) ** 0.5))
                y = min(y / 3.0, 1.0)
                if self.bias > 0:
                    y *= 0.45 + 0.55 * x
                elif self.bias < 0:
                    y *= 1.0 - 0.55 * x
            elif self.distribution == "gaussian":
                center = 0.5 + (self.bias / 100.0) * 0.5
                sigma = 0.20
                y = pow(2.718281828, -((x - center) ** 2) / (2 * sigma ** 2))
            else:
                if self.bias == 0:
                    y = 0.5
                elif self.bias > 0:
                    y = 0.15 + 0.85 * (x ** (1.0 / (1.0 + 4.0 * strength)))
                else:
                    y = 0.15 + 0.85 * ((1.0 - x) ** (1.0 / (1.0 + 4.0 * strength)))
            points.append((x, max(0.0, min(1.0, y))))

        max_y = max(y for _x, y in points) or 1.0
        path_points = []
        for x, y in points:
            px = plot.left() + x * plot.width()
            py = plot.bottom() - (y / max_y) * plot.height()
            path_points.append((px, py))

        painter.setPen(QColor(self.text_color))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index in range(1, len(path_points)):
            x1, y1 = path_points[index - 1]
            x2, y2 = path_points[index]
            painter.drawLine(x1, y1, x2, y2)


class RandomizerPage(QWidget):
    """MIDI randomizer settings and live test display."""

    def __init__(self, parent_dialog, parent=None):
        super().__init__(parent)

        self.parent_dialog = parent_dialog
        self.randomizer = randomizer

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        title = QLabel("MIDI Randomizer")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )

        description = QLabel(
            "Generate integer MIDI values from 0–127. "
            "The default interval is 30–97. "
            "The same value is never generated twice in a row."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #000000; font-size: 12px;"
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(4)

        range_group = QGroupBoxCompat("Randomization interval")
        range_layout = range_group.layout()

        self.range_slider = RangeSlider(
            0,
            127,
            self.randomizer.minimum,
            self.randomizer.maximum,
        )
        self.range_slider.setToolTip(
            "The generator selects values only within this range.\n"
            "0 is the lowest and 127 is the highest MIDI value."
        )
        self.range_slider.valuesChanged.connect(
            self._slider_changed
        )
        range_layout.addWidget(self.range_slider)

        values_row = QHBoxLayout()
        values_row.setContentsMargins(0, 0, 0, 0)
        values_row.setSpacing(8)

        values_row.addWidget(QLabel("Minimum:"))

        self.minimum_spin = QSpinBox()
        self.minimum_spin.setRange(0, 127)
        self.minimum_spin.setValue(self.randomizer.minimum)
        self.minimum_spin.setMaximumWidth(90)
        self.minimum_spin.setToolTip(
            "The lowest permitted MIDI value.\n"
            "The random value cannot be lower than this."
        )
        self.minimum_spin.valueChanged.connect(
            self._minimum_changed
        )
        values_row.addWidget(self.minimum_spin)

        values_row.addSpacing(12)
        values_row.addWidget(QLabel("Maximum:"))

        self.maximum_spin = QSpinBox()
        self.maximum_spin.setRange(0, 127)
        self.maximum_spin.setValue(self.randomizer.maximum)
        self.maximum_spin.setMaximumWidth(90)
        self.maximum_spin.setToolTip(
            "The highest permitted MIDI value.\n"
            "The random value cannot be higher than this."
        )
        self.maximum_spin.valueChanged.connect(
            self._maximum_changed
        )
        values_row.addWidget(self.maximum_spin)
        values_row.addStretch()

        range_layout.addLayout(values_row)
        layout.addWidget(range_group)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)

        reset = QPushButton("Reset to MIDI PAN Randomizer")
        reset.setMaximumWidth(220)
        reset.setToolTip(
            "Restores the recommended default interval for the PAN Randomizer by setting "
            "the Minimum and Maximum values."
        )
        reset.clicked.connect(self.reset_randomizer_default)
        action_row.addWidget(reset)
        action_row.addStretch()

        help_button = QPushButton("?")
        help_button.setMaximumWidth(28)
        help_button.clicked.connect(self.show_local_help)
        help_button.setToolTip("Local help")
        action_row.addWidget(help_button)

        layout.addLayout(action_row)
        layout.addStretch()

    def reset_randomizer_default(self):
        self._minimum_changed(32)
        self._maximum_changed(96)

    def show_local_help(self):
        QMessageBox.information(
            self,
            "PAN Randomizer Help",
            "MIDI PAN Randomizer\n\n"
            "Minimum and Maximum define the permitted range for generated MIDI values."
            "\n\n"
            "On the Randomization Behavior page, configure Distribution, "
            "Bias, Maximum Change, Humanize, repeat avoidance, and Interval.\n\n"
            "TEST updates only the random value and graph; it "
            "does not send MIDI messages to JACK MIDI OUT.\n\n"
            "While PLAY is active, RND PAN sends a separate CC10 Pan message "
            "on the same MIDI channel when a Note On event arrives.\n\n"
            "The main-window Width control expands or contracts the interval "
            "symmetrically while preserving its centre."
        )

    def _notify_range_changed(self):
        main_window = (
            self.parent_dialog.parent()
            if self.parent_dialog is not None
            else None
        )
        if main_window is not None and hasattr(
            main_window,
            "randomizer_range_changed_from_preferences",
        ):
            main_window.randomizer_range_changed_from_preferences()

    def _slider_changed(self, low, high):
        self.minimum_spin.blockSignals(True)
        self.maximum_spin.blockSignals(True)
        try:
            self.minimum_spin.setValue(low)
            self.maximum_spin.setValue(high)
        finally:
            self.minimum_spin.blockSignals(False)
            self.maximum_spin.blockSignals(False)

        self.randomizer.set_range(low, high)
        self._notify_range_changed()

    def _minimum_changed(self, value):
        if value > self.maximum_spin.value():
            self.maximum_spin.blockSignals(True)
            self.maximum_spin.setValue(value)
            self.maximum_spin.blockSignals(False)

        self.range_slider.set_values(
            value,
            self.maximum_spin.value(),
        )
        self.randomizer.set_range(
            value,
            self.maximum_spin.value(),
        )
        self._notify_range_changed()

    def _maximum_changed(self, value):
        if value < self.minimum_spin.value():
            self.minimum_spin.blockSignals(True)
            self.minimum_spin.setValue(value)
            self.minimum_spin.blockSignals(False)

        self.range_slider.set_values(
            self.minimum_spin.value(),
            value,
        )
        self.randomizer.set_range(
            self.minimum_spin.value(),
            value,
        )
        self._notify_range_changed()

class RandomizerBehaviorPage(QWidget):
    """Randomizer behavior controls in a compact 2x2 + Test layout."""

    PRESETS = (
        (
            "PAN — Default",
            {
                "minimum": 13,
                "maximum": 115,
                "distribution": "center",
                "bias": 0,
                "max_change": 100,
                "prevent_duplicates": True,
                "avoid_recent": False,
                "recent_history": 5,
                "interval_ms": 500,
                "humanize": 0,
            },
        ),
        (
            "PAN — Natural",
            {
                "minimum": 32,
                "maximum": 96,
                "distribution": "center",
                "bias": 0,
                "max_change": 12,
                "prevent_duplicates": True,
                "avoid_recent": True,
                "recent_history": 5,
                "interval_ms": 500,
                "humanize": 0,
            },
        ),
        (
            "PAN — Wide",
            {
                "minimum": 16,
                "maximum": 112,
                "distribution": "center",
                "bias": 0,
                "max_change": 18,
                "prevent_duplicates": True,
                "avoid_recent": True,
                "recent_history": 5,
                "interval_ms": 500,
                "humanize": 0,
            },
        ),
        (
            "PAN — Humanize Soft",
            {
                "minimum": 38,
                "maximum": 90,
                "distribution": "gaussian",
                "bias": 0,
                "max_change": 8,
                "prevent_duplicates": True,
                "avoid_recent": True,
                "recent_history": 4,
                "interval_ms": 400,
                "humanize": 4,
            },
        ),
        (
            "PAN — Humanize Hard",
            {
                "minimum": 8,
                "maximum": 119,
                "distribution": "uniform",
                "bias": 0,
                "max_change": 28,
                "prevent_duplicates": True,
                "avoid_recent": True,
                "recent_history": 7,
                "interval_ms": 600,
                "humanize": 8,
            },
        ),
    )

    def __init__(self, randomizer_instance, parent=None):
        super().__init__(parent)
        self.randomizer = randomizer_instance
        self.parent_dialog = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        title = QLabel("Randomization Behavior")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        description = QLabel(
            "Shape the probability distribution, limit movement from the "
            "previous value, control repeated values, and set the "
            "randomization interval."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #000000; font-size: 12px;")

        layout.addWidget(title)
        layout.addWidget(description)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # ---------------------------------------------------------------
        # Distribution — top left
        # ---------------------------------------------------------------
        distribution_group = QGroupBoxCompat("Distribution")
        distribution_layout = distribution_group.layout()

        distribution_row = QHBoxLayout()
        distribution_row.setContentsMargins(0, 0, 0, 0)
        distribution_row.setSpacing(6)
        distribution_row.addWidget(QLabel("Type:"))

        self.distribution_combo = QComboBox()
        for key, label in MidiRandomizer.DISTRIBUTIONS:
            self.distribution_combo.addItem(label, key)

        current_index = max(
            0,
            self.distribution_combo.findData(
                self.randomizer.distribution
            ),
        )
        self.distribution_combo.setCurrentIndex(current_index)
        self.distribution_combo.setToolTip(
            "Controls which values are more likely within the selected range.\n"
            "Uniform = all values have approximately equal probability.\n"
            "Center-biased = values near the centre are more likely.\n"
            "Edge-biased = values near the edges are more likely.\n"
            "Gaussian = bell curve; values near the centre are more likely."
        )
        self.distribution_combo.currentIndexChanged.connect(
            self.distribution_changed
        )
        distribution_row.addWidget(self.distribution_combo, 1)
        distribution_layout.addLayout(distribution_row)

        self.preview = DistributionPreview()
        self.preview.setMinimumHeight(70)
        self.preview.set_distribution(self.randomizer.distribution)
        self.preview.set_bias(self.randomizer.bias)
        distribution_layout.addWidget(self.preview)

        bias_row = QHBoxLayout()
        bias_row.setContentsMargins(0, 0, 0, 0)
        bias_row.setSpacing(5)
        bias_row.addWidget(QLabel("Bias:"))

        self.bias_slider = QSlider(Qt.Orientation.Horizontal)
        self.bias_slider.setRange(-100, 100)
        self.bias_slider.setToolTip(
            "Shifts the probability toward one side of the range.\n"
            "0 = no bias.\n"
            "Negative = favours lower values.\n"
            "Positive = favours higher values.\n"
            "Does not change the Minimum/Maximum boundaries."
        )
        self.bias_slider.setValue(self.randomizer.bias)
        self.bias_slider.valueChanged.connect(self.bias_changed)
        bias_row.addWidget(self.bias_slider, 1)

        self.bias_value = QLabel()
        self.bias_value.setMinimumWidth(38)
        self.bias_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.bias_value.setToolTip(
            "Bias amount:\n"
            "0 = semleges.\n"
            "Negative = lower values.\n"
            "Positive = higher values."
        )
        bias_row.addWidget(self.bias_value)
        distribution_layout.addLayout(bias_row)

        self._update_bias_label()
        grid.addWidget(distribution_group, 0, 0)

        # ---------------------------------------------------------------
        # Movement — top right
        # ---------------------------------------------------------------
        movement_group = QGroupBoxCompat("Movement")
        movement_layout = movement_group.layout()

        change_title = QLabel(
            "Maximum change from previous value:"
        )
        change_title.setWordWrap(True)
        movement_layout.addWidget(change_title)

        change_row = QHBoxLayout()
        change_row.setContentsMargins(0, 0, 0, 0)
        change_row.setSpacing(5)

        self.change_slider = QSlider(Qt.Orientation.Horizontal)
        self.change_slider.setRange(0, MIDI_MAX)
        self.change_slider.setToolTip(
            "Sets the maximum amount by which a new value may differ "
            "from the previously generated value.\n"
            "For example, with ±10, a value after 60 must be between 50 and 70.\n"
            "Unlimited disables this limit."
        )
        self.change_slider.setValue(self.randomizer.max_change)
        self.change_slider.valueChanged.connect(self.change_changed)
        change_row.addWidget(self.change_slider, 1)

        self.change_value = QLabel()
        self.change_value.setMinimumWidth(58)
        self.change_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        change_row.addWidget(self.change_value)
        movement_layout.addLayout(change_row)

        self.change_visual = QLabel()
        self.change_visual.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.change_visual.setMinimumHeight(40)
        self.change_visual.setWordWrap(True)
        self.change_visual.setToolTip(
            "Shows which next values are allowed based on the previous value "
            "and the current limit."
        )
        movement_layout.addWidget(self.change_visual)
        self._update_change_display()

        humanize_row = QHBoxLayout()
        humanize_row.setContentsMargins(0, 0, 0, 0)
        humanize_row.setSpacing(5)
        humanize_row.addWidget(QLabel("Humanize:"))

        self.humanize_spin = QSpinBox()
        self.humanize_spin.setRange(0, 64)
        self.humanize_spin.setValue(self.randomizer.humanize)
        self.humanize_spin.setToolTip(
            "Adds a random deviation around the incoming MIDI value.\n"
            "0 = Original, vagyis nincs Humanize.\n"
            "For example, ±5 allows the output to differ from the input by up to 5.\n"
            "The result remains within the MIDI range of 0–127."
        )
        self.humanize_spin.valueChanged.connect(self.humanize_changed)
        humanize_row.addWidget(self.humanize_spin)
        humanize_row.addStretch()
        movement_layout.addLayout(humanize_row)

        humanize_hint = QLabel(
            "Humanize = deviation around the original input value."
        )
        humanize_hint.setWordWrap(True)
        humanize_hint.setStyleSheet("color: #555555; font-size: 11px;")
        movement_layout.addWidget(humanize_hint)

        grid.addWidget(movement_group, 0, 1)

        # ---------------------------------------------------------------
        # Repetition — bottom left
        # ---------------------------------------------------------------
        repetition_group = QGroupBoxCompat("Repetition")
        repetition_layout = repetition_group.layout()

        self.duplicate_checkbox = QCheckBox(
            "Prevent consecutive duplicates"
        )
        self.duplicate_checkbox.setChecked(
            self.randomizer.prevent_duplicates
        )
        self.duplicate_checkbox.setToolTip(
            "Prevents the same value from occurring twice in a row "
            "megjelenjen.\n"
            "This applies only to the immediately preceding value."
        )
        self.duplicate_checkbox.toggled.connect(
            self.randomizer.set_prevent_duplicates
        )
        repetition_layout.addWidget(self.duplicate_checkbox)

        recent_row = QHBoxLayout()
        recent_row.setContentsMargins(0, 0, 0, 0)
        recent_row.setSpacing(6)

        self.recent_checkbox = QCheckBox(
            "Avoid recent values"
        )
        self.recent_checkbox.setChecked(
            self.randomizer.avoid_recent
        )
        self.recent_checkbox.setToolTip(
            "Temporarily excludes the specified number of most recent values.\n"
            "This prevents the generator from returning too quickly to the same "
            "values."
        )
        self.recent_checkbox.toggled.connect(
            self._recent_enabled_changed
        )
        recent_row.addWidget(self.recent_checkbox)

        recent_row.addWidget(QLabel("History:"))

        self.history_spin = QSpinBox()
        self.history_spin.setRange(1, 32)
        self.history_spin.setValue(self.randomizer.recent_history)
        self.history_spin.setMaximumWidth(68)
        self.history_spin.setToolTip(
            "The number of most recently generated values to exclude.\n"
            "For example, 5 tells it to avoid the last five values."
        )
        self.history_spin.valueChanged.connect(
            self.history_changed
        )
        recent_row.addWidget(self.history_spin)
        recent_row.addStretch()

        repetition_layout.addLayout(recent_row)
        self.history_spin.setEnabled(self.randomizer.avoid_recent)

        grid.addWidget(repetition_group, 1, 0)

        # ---------------------------------------------------------------
        # Randomization Interval — bottom right
        # ---------------------------------------------------------------
        interval_group = QGroupBoxCompat("Randomization Interval")
        interval_layout = interval_group.layout()

        interval_row = QHBoxLayout()
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(6)
        interval_row.addWidget(QLabel("Interval:"))

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(300, 3000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setValue(
            max(300, min(3000, self.randomizer.interval_ms))
        )
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setMaximumWidth(105)
        self.interval_spin.setToolTip(
            "The interval between generated values.\n"
            "300 ms = 0.3 seconds; 3000 ms = 3 seconds.\n"
            "Lower values produce faster generation."
        )
        self.interval_spin.valueChanged.connect(self.interval_changed)
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        interval_layout.addLayout(interval_row)

        interval_hint = QLabel(
            "Base interval used by the randomizer. "
            "The Speed Test slider below controls the same value."
        )
        interval_hint.setWordWrap(True)
        interval_hint.setStyleSheet("color: #555555; font-size: 11px;")
        interval_hint.setToolTip(
            "This duration determines how often a new random value is generated.\n"
            "Speed Test sets the generation interval for TEST; it is separate from the main-window Speed control."
        )
        interval_layout.addWidget(interval_hint)

        grid.addWidget(interval_group, 1, 1)

        layout.addLayout(grid)

        # ---------------------------------------------------------------
        # Test — full width below the 2x2 grid
        # ---------------------------------------------------------------
        test_group = QGroupBoxCompat("Test")
        test_layout = test_group.layout()

        result_row = QHBoxLayout()
        result_row.setContentsMargins(0, 0, 0, 0)
        result_row.setSpacing(8)

        result_row.addWidget(QLabel("Generated:"))

        result_row.addSpacing(8)
        result_row.addWidget(QLabel("Speed Test:"))

        self.interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.interval_slider.setRange(300, 3000)
        self.interval_slider.setSingleStep(100)
        self.interval_slider.setPageStep(500)
        self.interval_slider.setValue(self.randomizer.interval_ms)
        self.interval_slider.setToolTip(
            "Speed Test: set how quickly the generated value changes during the test "
            ".\n"
            "0,3 s a leggyorsabb, 3,0 s a leglassabb.\n"
            "Default: 0.5 s."
        )
        self.interval_slider.valueChanged.connect(
            self.interval_changed
        )
        result_row.addWidget(self.interval_slider, 1)

        self.interval_value = QLabel()
        self.interval_value.setMinimumWidth(48)
        self.interval_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        result_row.addWidget(self.interval_value)
        self._update_interval_label()

        self.result_label = QLabel("—")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_font = self.result_label.font()
        result_font.setPointSize(22)
        result_font.setBold(True)
        self.result_label.setFont(result_font)
        self.result_label.setToolTip(
            "The most recently generated MIDI value.\n"
            "This value becomes the randomizer’s current output."
        )
        result_row.addWidget(self.result_label, 0)

        self.test_button = QPushButton("TEST")
        self.test_button.setCheckable(True)
        self.test_button.setToolTip(
            "Starts or stops test generation.\n"
            "The Speed Test slider controls the rate.\n"
            "TEST does not send MIDI to JACK MIDI OUT; it only updates "
            "the Generated value and the graph."
        )
        self.test_button.clicked.connect(self.toggle_test)
        result_row.addWidget(self.test_button)

        test_layout.addLayout(result_row)
        layout.addWidget(test_group)

        self.test_timer = QTimer(self)
        self.test_timer.setInterval(self.randomizer.interval_ms)
        self.test_timer.timeout.connect(self.generate_test_value)

        # ---------------------------------------------------------------
        # Recommended presets — convenience selector
        # ---------------------------------------------------------------
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)

        preset_label = QLabel("Recommended settings:")
        preset_label.setToolTip(
            "Ready-made suggestions for musical use. Selecting one does not add "
            "a new randomization mode; it configures the existing "
            "Minimum/Maximum, Distribution, Bias, Movement, Repetition "
            "and Interval controls."
        )
        preset_row.addWidget(preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— Select a recommendation —", None)
        for preset_name, preset_values in self.PRESETS:
            self.preset_combo.addItem(preset_name, preset_values)
        self.preset_combo.setToolTip(
            "Choose a ready-made behaviour profile. "
            "The preset sets all related parameters at once."
        )
        self.preset_combo.currentIndexChanged.connect(
            self.preset_changed
        )
        preset_row.addWidget(self.preset_combo, 1)

        self.preset_help_button = QPushButton("?")
        self.preset_help_button.setFixedSize(26, 26)
        self.preset_help_button.setToolTip(
            "A short description of the currently selected preset."
        )
        self.preset_help_button.clicked.connect(
            self.show_preset_help
        )
        preset_row.addWidget(self.preset_help_button)

        self._preset_descriptions = {'PAN — Default': 'A balanced default PAN profile for live performance: center-biased distribution, range 13–115, maximum change ±100, and width ±51.', 'PAN — Natural': 'A natural PAN profile with controlled stereo movement around the centre.', 'PAN — Wide': 'A wide PAN profile with greater stereo movement while retaining a centre-biased distribution.', 'PAN — Humanize Soft': 'Subtle humanization: narrower range, Gaussian distribution, smaller changes, and ±4 deviation around the input.', 'PAN — Humanize Hard': 'Stronger humanization: wider range, Uniform distribution, larger changes, and ±8 deviation around the input.'}

        # The first item is a live status indicator: it tells the user
        # whether the current controls match one of the recommendations.
        self.preset_combo.setItemText(
            0, "Custom — current settings"
        )

        layout.addLayout(preset_row)

        self._connect_range_status_updates()
        self._update_preset_status()

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)

        self.output_status_title = QLabel("Output:")
        self.output_status_label = QLabel()
        self.output_status_label.setToolTip(
            "Follows the main-window Play/Stop button."
        )
        self.output_status_label.setMinimumWidth(64)
        self.output_status_label.setStyleSheet("font-weight: bold;")

        main_window = (
            self.parent_dialog.parent()
            if self.parent_dialog is not None
            else None
        )
        self.set_output_running(
            bool(
                main_window is not None
                and hasattr(main_window, "randomizer_start_button")
                and main_window.randomizer_start_button.isChecked()
            )
        )

        buttons_row.addWidget(self.output_status_title)
        buttons_row.addWidget(self.output_status_label)
        buttons_row.addStretch()

        reset = QPushButton("Reset behavior to default")
        reset.setMaximumWidth(190)
        reset.clicked.connect(self.reset_default)
        buttons_row.addWidget(reset)

        help_button = QPushButton("?")
        help_button.setMaximumWidth(28)
        help_button.clicked.connect(self.show_local_help)
        help_button.setToolTip("Local help")
        buttons_row.addWidget(help_button)

        layout.addLayout(buttons_row)

    def show_local_help(self):
        QMessageBox.information(
            self,
            "Randomization Behavior Help",
            "Randomization Behavior\n\n"
            "Configure the distribution, Bias, Maximum Change, repeat and recent-value avoidance, and timing.\n\n"
            "TEST updates the generated random value and graph only. It does NOT send MIDI messages to JACK MIDI OUT.\n\n"
            "Actual MIDI processing occurs only while PLAY is active and an incoming Note On event is processed.\n\n"
            "Serial chain: MIDI source -> RND PAN -> RND VEL -> destination. The Note On passes through the chain once; RND PAN adds a separate CC10 Pan event, while RND VEL modifies Note On velocity.\n\n"
            "In a parallel setup, both branches receive the original Note On. If they share a destination, separate Note On events may arrive. A serial connection is recommended for combined processing."
        )

    def set_output_running(self, running):
        self.output_status_label.setText(
            "RUNNING" if bool(running) else "STOPPED"
        )

    def show_preset_help(self):
        index = self.preset_combo.currentIndex()
        name = self.preset_combo.currentText()
        if index <= 0 or not name:
            name = "Custom"
            text = (
                "Custom represents the current manually configured values."
                "jelenti."
            )
        else:
            text = self._preset_descriptions.get(
                name,
                "The preset sets all related parameters at once.",
            )

        popup = QFrame(
            self,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        popup.setFrameShape(QFrame.Shape.StyledPanel)
        popup.setStyleSheet(
            "QFrame { background: white; border: 1px solid #777777; "
            "border-radius: 4px; } "
            "QLabel#presetHelpTitle { font-weight: bold; }"
        )

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(10, 8, 10, 8)
        popup_layout.setSpacing(5)

        title = QLabel(name)
        title.setObjectName("presetHelpTitle")
        popup_layout.addWidget(title)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setMaximumWidth(360)
        popup_layout.addWidget(body)

        values = self.preset_combo.itemData(index)
        if values:
            humanize = values["humanize"]
            humanize_text = (
                "Original (±0)" if humanize == 0 else f"±{humanize}"
            )
            detail = QLabel(
                f"Range: {values['minimum']}–{values['maximum']}  |  "
                f"Distribution: {values['distribution']}  |  "
                f"Bias: {values['bias']:+d}\n"
                f"Max. Change: ±{values['max_change']}  |  "
                f"Humanize: {humanize_text}  |  "
                f"Interval: {values['interval_ms']} ms"
            )
            detail.setWordWrap(True)
            detail.setStyleSheet("font-size: 11px; color: #444444;")
            popup_layout.addWidget(detail)

        popup.adjustSize()
        pos = self.preset_help_button.mapToGlobal(
            QPointF(0, self.preset_help_button.height()).toPoint()
        )
        popup.move(pos)
        popup.show()

    def preset_changed(self, index):
        preset = self.preset_combo.itemData(index)
        if not preset:
            return

        self.stop_test()

        # Range belongs to the existing Randomizer page. Update its existing
        # controls through the same public handlers used by the GUI.
        randomizer_page = getattr(self.parent_dialog, "randomizer_page", None)
        if randomizer_page is not None:
            randomizer_page._minimum_changed(preset["minimum"])
            randomizer_page._maximum_changed(preset["maximum"])

        self.distribution_combo.setCurrentIndex(
            self.distribution_combo.findData(preset["distribution"])
        )
        self.bias_slider.setValue(preset["bias"])
        self.change_slider.setValue(preset["max_change"])
        self.duplicate_checkbox.setChecked(
            preset["prevent_duplicates"]
        )
        self.recent_checkbox.setChecked(
            preset["avoid_recent"]
        )
        self.history_spin.setValue(preset["recent_history"])
        self.interval_spin.setValue(preset["interval_ms"])
        self.interval_slider.setValue(preset["interval_ms"])

        # Humanize is not represented by another widget signal here, so set
        # the live randomizer explicitly. This keeps Preferences, the main
        # window and the actual MIDI processing on the same value.
        self.randomizer.set_humanize(preset["humanize"])
        self.humanize_spin.blockSignals(True)
        try:
            self.humanize_spin.setValue(preset["humanize"])
        finally:
            self.humanize_spin.blockSignals(False)

        # Refresh the main window immediately while preserving PLAY/STOP.
        main_window = (
            self.parent_dialog.parent()
            if self.parent_dialog is not None
            else None
        )
        if main_window is not None:
            if hasattr(main_window, "_sync_main_knobs"):
                main_window._sync_main_knobs()
            if hasattr(main_window, "_sync_main_preset_status"):
                main_window._sync_main_preset_status()
            if hasattr(main_window, "persist_randomizer_settings"):
                main_window.persist_randomizer_settings()

        self._update_preset_status()

        # One consolidated preset log: the complete preset state is recorded
        # after all controls have been applied.
        if index > 0:
            main_window = (
                self.parent_dialog.parent()
                if self.parent_dialog is not None
                else None
            )
            backend = getattr(main_window, "backend", None)
            if backend is not None and hasattr(backend, "debug_log"):
                values = self.preset_combo.itemData(index)
                humanize_text = (
                    "Original (±0)"
                    if values["humanize"] == 0
                    else f"±{values['humanize']}"
                )
                backend.debug_log(
                    f"{APP_TITLE}: PRESET → {self.preset_combo.currentText()} | "
                    f"Range {values['minimum']}–{values['maximum']} | "
                    f"Distribution {values['distribution']} | "
                    f"Bias {values['bias']:+d} | "
                    f"Max. Change ±{values['max_change']} | "
                    f"Prevent duplicates "
                    f"{'ON' if values['prevent_duplicates'] else 'OFF'} | "
                    f"Avoid recent "
                    f"{'ON' if values['avoid_recent'] else 'OFF'} | "
                    f"History {values['recent_history']} | "
                    f"Humanize {humanize_text} | "
                    f"Interval {values['interval_ms']} ms"
                )

    def _connect_range_status_updates(self):
        randomizer_page = getattr(
            self.parent_dialog, "randomizer_page", None
        )
        if randomizer_page is None:
            return

        for widget in (
            getattr(randomizer_page, "minimum_spin", None),
            getattr(randomizer_page, "maximum_spin", None),
        ):
            if widget is not None:
                widget.valueChanged.connect(
                    lambda _value: self._update_preset_status()
                )

    def _current_preset_values(self):
        randomizer_page = getattr(
            self.parent_dialog, "randomizer_page", None
        )
        if randomizer_page is None:
            return None

        return {
            "minimum": randomizer_page.minimum_spin.value(),
            "maximum": randomizer_page.maximum_spin.value(),
            "distribution": self.distribution_combo.currentData(),
            "bias": self.bias_slider.value(),
            "max_change": self.change_slider.value(),
            "prevent_duplicates": self.duplicate_checkbox.isChecked(),
            "avoid_recent": self.recent_checkbox.isChecked(),
            "recent_history": self.history_spin.value(),
            "interval_ms": self.interval_spin.value(),
            "humanize": self.humanize_spin.value(),
        }

    def _persist_randomizer_settings(self):
        main_window = (
            self.parent_dialog.parent()
            if self.parent_dialog is not None
            else None
        )
        if main_window is not None and hasattr(
            main_window,
            "persist_randomizer_settings",
        ):
            main_window.persist_randomizer_settings()

    def _sync_main_window_live(self):
        main_window = (
            self.parent_dialog.parent()
            if self.parent_dialog is not None
            else None
        )
        if main_window is None:
            return

        if hasattr(main_window, "_sync_main_knobs"):
            main_window._sync_main_knobs()
        if hasattr(main_window, "_sync_main_preset_status"):
            main_window._sync_main_preset_status()
        if hasattr(main_window, "randomizer_timer"):
            main_window.randomizer_timer.setInterval(
                self.randomizer.interval_ms
            )

    def _update_preset_status(self):
        current = self._current_preset_values()
        if current is None:
            return

        matched_name = None
        for preset_name, preset_values in self.PRESETS:
            if current == preset_values:
                matched_name = preset_name
                break

        self.preset_combo.blockSignals(True)
        try:
            if matched_name is None:
                self.preset_combo.setCurrentIndex(0)
                self.preset_combo.setItemText(
                    0, "Custom — current settings"
                )
            else:
                index = self.preset_combo.findText(matched_name)
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
        finally:
            self.preset_combo.blockSignals(False)

        main_window = (
            self.parent_dialog.parent()
            if self.parent_dialog is not None
            else None
        )
        if main_window is not None and hasattr(
            main_window, "_sync_main_preset_status"
        ):
            main_window._sync_main_preset_status()

    def distribution_changed(self, index):
        distribution = self.distribution_combo.itemData(index)
        self.randomizer.set_distribution(distribution)
        self.preview.set_distribution(distribution)
        self._update_preset_status()
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def bias_changed(self, value):
        self.randomizer.set_bias(value)
        self._update_bias_label()
        self.preview.set_bias(value)
        self._update_preset_status()
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def _update_bias_label(self):
        value = self.randomizer.bias
        if value == 0:
            text = "0"
        elif value > 0:
            text = f"+{value}"
        else:
            text = str(value)
        self.bias_value.setText(text)

    def change_changed(self, value):
        self.randomizer.set_max_change(value)
        self._update_change_display()
        self._update_preset_status()
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def humanize_changed(self, value):
        self.randomizer.set_humanize(value)
        self._update_preset_status()
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def _update_change_display(self):
        value = self.randomizer.max_change
        if value >= MIDI_MAX:
            text = "Unlimited"
        else:
            text = f"±{value}"
        self.change_value.setText(text)

        if self.randomizer.last_value is None:
            example = "Previous → next: not generated yet"
        else:
            lo = max(
                self.randomizer.minimum,
                self.randomizer.last_value - value,
            )
            hi = min(
                self.randomizer.maximum,
                self.randomizer.last_value + value,
            )
            example = (
                f"Previous: {self.randomizer.last_value}   "
                f"Allowed next: {lo}–{hi}"
            )
        self.change_visual.setText(example)

    def history_changed(self, value):
        self.randomizer.set_recent_history(value)
        self._update_preset_status()
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def _recent_enabled_changed(self, checked):
        self.randomizer.set_avoid_recent(
            checked,
            self.history_spin.value(),
        )
        self.history_spin.setEnabled(checked)
        self._update_preset_status()
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def _update_interval_label(self):
        seconds = self.randomizer.interval_ms / 1000.0
        self.interval_value.setText(f"{seconds:.1f} s")

    def interval_changed(self, value):
        value = max(300, min(3000, int(value)))
        self.randomizer.set_interval(value)

        if hasattr(self, "interval_slider"):
            self.interval_slider.blockSignals(True)
            try:
                self.interval_slider.setValue(value)
            finally:
                self.interval_slider.blockSignals(False)

        if hasattr(self, "interval_spin"):
            self.interval_spin.blockSignals(True)
            try:
                self.interval_spin.setValue(value)
            finally:
                self.interval_spin.blockSignals(False)

        self._update_interval_label()
        self._update_preset_status()
        if hasattr(self, "test_timer"):
            self.test_timer.setInterval(value)
        self._persist_randomizer_settings()
        self._sync_main_window_live()

    def toggle_test(self, checked):
        if checked:
            self.test_button.setText("STOP")
            self.generate_test_value()
            self.test_timer.setInterval(
                self.randomizer.interval_ms
            )
            self.test_timer.start()
        else:
            self.test_button.setText("TEST")
            self.test_timer.stop()

    def generate_test_value(self):
        value = self.randomizer.generate()
        self.result_label.setText(str(value))
        if self.parent_dialog is not None:
            self.parent_dialog.midi_pan = value
            main_window = self.parent_dialog.parent()
            if main_window is not None and hasattr(
                main_window, "add_randomizer_value"
            ):
                main_window.add_randomizer_value(value)
        self._update_change_display()

    def stop_test(self):
        self.test_timer.stop()
        self.test_button.setChecked(False)
        self.test_button.setText("TEST")

    def reset_default(self):
        self.stop_test()
        self.distribution_combo.setCurrentIndex(
            self.distribution_combo.findData("uniform")
        )
        self.bias_slider.setValue(0)
        self.change_slider.setValue(MIDI_MAX)
        self.duplicate_checkbox.setChecked(True)
        self.recent_checkbox.setChecked(False)
        self.history_spin.setValue(5)
        self.interval_slider.setValue(500)
        self.randomizer.reset_history()
        if self.parent_dialog is not None:
            main_window = self.parent_dialog.parent()
            if main_window is not None and hasattr(
                main_window, "clear_randomizer_graph"
            ):
                main_window.clear_randomizer_graph()
        self._update_change_display()
        self.history_spin.setEnabled(False)
        self.test_button.setChecked(False)
        self.test_button.setText("TEST")
        self.test_timer.stop()
        self._update_preset_status()


class PreferencesDialog(QDialog):
    """Settings panel based on the working SysEx Filter panel."""

    def __init__(
        self,
        backend,
        current_size,
        default_size,
        resizable,
        layout_mode,
        window_width,
        background_color,
        button_background_color,
        button_text_color,
        combo_background_color,
        combo_text_color,
        graph_background_color,
        graph_text_color,
        graph_grid_color,
        graph_axis_color,
        graph_point_color,
        window_text_background_color,
        window_text_color,
        pot_value_text_color,
        pot_caption_text_color,
        range_text_color,
        arrow_background_color,
        arrow_text_color,
        distribution_graph_background_color,
        distribution_graph_text_color,
        reset_graph_on_left_click,
        debug_to_terminal,
        graph_beats=DEFAULT_GRAPH_BEATS,
        frameless_window=False,
        show_current_rnd_value=DEFAULT_SHOW_CURRENT_RND_VALUE,
        rnd_value_color=DEFAULT_RND_VALUE_COLOR,
        rnd_value_size=DEFAULT_RND_VALUE_SIZE,
        open_terminal_for_debug=False,
        debug_panel_rows=5,
        parent=None,
    ):
        super().__init__(parent)

        self.backend = backend
        self.main_window = parent
        self.selected_size = None
        self.selected_resizable = None
        self.selected_layout = None

        self.setWindowTitle(
            "MIDI Randomize Preferences"
        )
        self.setModal(True)
        self.resize(700, 633)
        self.setMinimumSize(620, 531)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            8, 8, 8, 8
        )
        root.setSpacing(6)

        intro = QLabel(
            "Configure the JACK MIDI environment "
            "and MIDI Patchbay window."
        )
        root.addWidget(intro)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(
            0, 0, 0, 0
        )
        body_layout.setSpacing(6)

        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(
            0, 0, 0, 0
        )
        nav_layout.setSpacing(2)

        self.page_buttons = []
        self.pages = QStackedWidget()

        page_definitions = (
            (
                "MIDI Input",
                lambda: MidiPortPage(
                    self,
                    "input",
                ),
                "go-down",
                QStyle.StandardPixmap.SP_ArrowDown,
            ),
            (
                "MIDI Output",
                lambda: MidiPortPage(
                    self,
                    "output",
                ),
                "go-up",
                QStyle.StandardPixmap.SP_ArrowUp,
            ),
            (
                "Layouts",
                lambda: LayoutsPage(
                    main_window=self.main_window,
                    show_graph=self.main_window.show_graph,
                    show_controls=self.main_window.show_controls,
                    show_interval=self.main_window.show_interval,
                    start_in_play=self.main_window.start_in_play,
                ),
                "view-grid",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
            (
                "MIDI Filter",
                lambda: MidiFilterPage(
                    self.backend,
                ),
                "view-filter",
                QStyle.StandardPixmap.SP_FileDialogContentsView,
            ),
            (
                "Randomizer",
                lambda: RandomizerPage(
                    self,
                ),
                "media-playlist-shuffle",
                QStyle.StandardPixmap.SP_BrowserReload,
            ),
            (
                "Randomizer Behavior",
                lambda: RandomizerBehaviorPage(
                    randomizer,
                    self,
                ),
                "preferences-system",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
            (
                "Display",
                lambda: DisplayPage(
                    window_width,
                    background_color,
                    button_background_color,
                    button_text_color,
                    combo_background_color,
                    combo_text_color,
                    self.main_window.graph_background_color,
                    graph_text_color,
                    self.main_window.graph_grid_color,
                    self.main_window.graph_axis_color,
                    self.main_window.graph_point_color,
                    self.main_window.window_text_background_color,
                    self.main_window.window_text_color,
                    self.main_window.pot_value_text_color,
                    self.main_window.pot_caption_text_color,
                    self.main_window.range_text_color,
                    self.main_window.arrow_background_color,
                    self.main_window.arrow_text_color,
                    self.main_window.distribution_graph_background_color,
                    self.main_window.distribution_graph_text_color,
                    reset_graph_on_left_click,
                    debug_to_terminal,
                    graph_beats,
                    self.main_window._frameless,
                    self.main_window.show_current_rnd_value,
                    self.main_window.rnd_value_color,
                    self.main_window.rnd_value_size,
                    open_terminal_for_debug,
                    debug_panel_rows,
                    self.main_window,
                ),
                "preferences-desktop-display",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
        )

        for index, (
            label,
            builder,
            theme_icon,
            fallback_icon,
        ) in enumerate(page_definitions):

            button = QPushButton(label)

            icon = QIcon.fromTheme(
                theme_icon
            )

            if icon.isNull():
                icon = self.style().standardIcon(
                    fallback_icon
                )

            button.setIcon(icon)
            button.setIconSize(
                QSize(18, 18)
            )
            button.setCheckable(True)
            button.setMinimumHeight(28)
            button.setFocusPolicy(
                Qt.FocusPolicy.NoFocus
            )
            button.setToolTip(
                wrapped_tooltip(
                    f"Preferences oldal — {label}\n"
                    "Opens the selected settings page."
                )
            )

            button.clicked.connect(
                lambda checked=False,
                page=index:
                self.select_page(page)
            )

            nav_layout.addWidget(button)
            self.page_buttons.append(
                button
            )

            page_scroll = QScrollArea()
            page_scroll.setWidgetResizable(
                True
            )
            page_scroll.setFrameShape(
                QFrame.Shape.NoFrame
            )
            page_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            page_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )

            built_page = builder()

            # Keep references so the live refresh timer can update them.
            if label == "MIDI Input":
                self.input_page = built_page
            elif label == "MIDI Output":
                self.output_page = built_page
            elif label == "Layouts":
                self.layouts_page = built_page
            elif label == "MIDI Filter":
                self.filter_page = built_page
            elif label == "Randomizer":
                self.randomizer_page = built_page
            elif label == "Randomizer Behavior":
                self.randomizer_behavior_page = built_page
            elif label == "Display":
                self.display_page = built_page

            page_scroll.setWidget(
                built_page
            )
            self.pages.addWidget(
                page_scroll
            )

        nav_layout.addStretch()

        nav_widget = QWidget()
        nav_widget.setFixedWidth(175)
        nav_widget.setLayout(
            nav_layout
        )

        body_layout.addWidget(
            nav_widget
        )
        body_layout.addWidget(
            self.pages,
            1
        )

        root.addWidget(
            body,
            1
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(
            self.save_and_close
        )
        root.addWidget(buttons)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(
            self.refresh_ports
        )
        self.refresh_timer.start()

        self.select_page(0)
        apply_wrapped_tooltips(self)

    @staticmethod
    def page_title(text):
        label = QLabel(text)
        label.setStyleSheet(
            "font-weight: bold;"
        )
        return label

    def select_page(self, index):
        self.pages.setCurrentIndex(index)

        for row, button in enumerate(
            self.page_buttons
        ):
            button.setChecked(
                row == index
            )

    def refresh_ports(self):
        if hasattr(self, "input_page"):
            self.input_page.refresh()

        if hasattr(self, "output_page"):
            self.output_page.refresh()

    def sync_window_width(self, width):
        display_page = getattr(
            self,
            "display_page",
            None,
        )
        if display_page is None:
            return

        width_spin = getattr(
            display_page,
            "width_spin",
            None,
        )
        if width_spin is None:
            return

        width_spin.blockSignals(True)
        try:
            width_spin.setValue(
                max(
                    MIN_SIZE,
                    min(
                        MAX_SIZE,
                        int(width),
                    ),
                )
            )
        finally:
            width_spin.blockSignals(False)

    def sync_graph_beats(self, beats):
        display_page = getattr(self, "display_page", None)
        if display_page is None:
            return

        spin = getattr(display_page, "graph_beats_spin", None)
        if spin is None:
            return

        spin.blockSignals(True)
        try:
            spin.setValue(
                max(
                    1,
                    min(
                        GRAPH_MAX_POINTS,
                        int(beats),
                    ),
                )
            )
        finally:
            spin.blockSignals(False)

    def sync_layout_settings(self, layout_mode, resizable):
        layouts_page = getattr(
            self,
            "layouts_page",
            None,
        )
        if layouts_page is None:
            return

        layouts_page.sync_from_main(
            layout_mode,
            resizable,
        )

    def save_and_close(self):
        self.selected_size = self.layouts_page.value()
        self.selected_resizable = self.layouts_page.resizable()
        self.selected_layout = self.layouts_page.layout_mode()

        (
            self.selected_window_width,
            self.selected_background_color,
            self.selected_button_background_color,
            self.selected_button_text_color,
            self.selected_combo_background_color,
            self.selected_combo_text_color,
            self.selected_graph_background_color,
            self.selected_graph_text_color,
            self.selected_graph_grid_color,
            self.selected_graph_axis_color,
            self.selected_graph_point_color,
            self.selected_window_text_background_color,
            self.selected_window_text_color,
            self.selected_pot_value_text_color,
            self.selected_pot_caption_text_color,
            self.selected_range_text_color,
            self.selected_arrow_background_color,
            self.selected_arrow_text_color,
            self.selected_distribution_graph_background_color,
            self.selected_distribution_graph_text_color,
            self.selected_reset_graph_on_left_click,
            self.selected_debug_to_terminal,
            self.selected_graph_beats,
            self.selected_frameless_window,
            self.selected_show_current_rnd_value,
            self.selected_rnd_value_color,
            self.selected_rnd_value_size,
        ) = self.display_page.values()

        self.filter_page.sync_filter()
        self.refresh_timer.stop()
        self.accept()

    def done(self, result):
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.stop()
        if hasattr(self, "randomizer_page"):
            if hasattr(self.randomizer_page, "stop_test"):
                self.randomizer_page.stop_test()
        if hasattr(self, "randomizer_behavior_page"):
            self.randomizer_behavior_page.stop_test()
        super().done(result)


class DisplayPage(QWidget):
    """Display and terminal debug settings for MIDI Randomize."""

    def __init__(
        self,
        window_width,
        background_color,
        button_background_color,
        button_text_color,
        combo_background_color,
        combo_text_color,
        graph_background_color,
        graph_text_color,
        graph_grid_color,
        graph_axis_color,
        graph_point_color,
        window_text_background_color,
        window_text_color,
        pot_value_text_color,
        pot_caption_text_color,
        range_text_color,
        arrow_background_color,
        arrow_text_color,
        distribution_graph_background_color,
        distribution_graph_text_color,
        reset_graph_on_left_click,
        debug_to_terminal,
        graph_beats=DEFAULT_GRAPH_BEATS,
        frameless_window=False,
        show_current_rnd_value=DEFAULT_SHOW_CURRENT_RND_VALUE,
        rnd_value_color=DEFAULT_RND_VALUE_COLOR,
        rnd_value_size=DEFAULT_RND_VALUE_SIZE,
        open_terminal_for_debug=False,
        debug_panel_rows=5,
        parent=None,
    ):
        super().__init__(parent)
        self.main_window = parent
        self.graph_background_color = graph_background_color
        self.graph_grid_color = graph_grid_color
        self.graph_axis_color = graph_axis_color
        self.graph_point_color = graph_point_color
        self.window_text_background_color = window_text_background_color
        self.window_text_color = window_text_color
        self.pot_value_text_color = pot_value_text_color
        self.pot_caption_text_color = pot_caption_text_color
        self.range_text_color = range_text_color
        self.arrow_background_color = arrow_background_color
        self.arrow_text_color = arrow_text_color
        self.distribution_graph_background_color = (
            distribution_graph_background_color
        )
        self.distribution_graph_text_color = (
            distribution_graph_text_color
        )
        self.graph_beats = max(
            1,
            min(
                GRAPH_MAX_POINTS,
                int(graph_beats),
            ),
        )
        self.show_current_rnd_value = bool(show_current_rnd_value)
        self.rnd_value_color = rnd_value_color
        self.rnd_value_size = max(
            10,
            min(100, int(rnd_value_size)),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        title = QLabel("Display")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        description = QLabel(
            "Configure the window, controls, colors, and terminal debug logging."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #000000; font-size: 12px;"
        )

        width_row = QHBoxLayout()
        width_row.setContentsMargins(0, 0, 0, 0)
        width_row.setSpacing(6)
        width_row.addWidget(QLabel("Window Width:"))

        self.width_spin = QSpinBox()
        self.width_spin.setRange(MIN_SIZE, MAX_SIZE)
        self.width_spin.setValue(
            max(
                MIN_SIZE,
                min(MAX_SIZE, int(window_width)),
            )
        )
        self.width_spin.setSuffix(" px")
        self.width_spin.setMaximumWidth(140)
        self.width_spin.valueChanged.connect(
            self.main_window.set_window_width
        )
        width_row.addWidget(self.width_spin)
        width_row.addStretch()

        beats_row = QHBoxLayout()
        beats_row.setContentsMargins(0, 0, 0, 0)
        beats_row.setSpacing(6)
        beats_row.addWidget(QLabel("Graph Beats:"))

        self.graph_beats_spin = QSpinBox()
        self.graph_beats_spin.setRange(1, GRAPH_MAX_POINTS)
        self.graph_beats_spin.setValue(self.graph_beats)
        self.graph_beats_spin.setMaximumWidth(100)
        self.graph_beats_spin.setToolTip(
            wrapped_tooltip(
                "Graph Beats\n"
                "The number of most recent values shown on the graph at once. "
                "generated MIDI values.\n"
                f"Valid range: 1–{GRAPH_MAX_POINTS}.\n"
                f"Default: {DEFAULT_GRAPH_BEATS}."
            )
        )
        self.graph_beats_spin.valueChanged.connect(
            self.main_window.set_graph_beats
        )
        beats_row.addWidget(self.graph_beats_spin)
        beats_row.addStretch()

        self.reset_graph_checkbox = QCheckBox(
            "Reset graph on left click"
        )
        self.reset_graph_checkbox.setChecked(
            bool(reset_graph_on_left_click)
        )
        self.reset_graph_checkbox.stateChanged.connect(
            self.main_window.set_reset_graph_on_left_click
        )

        self.frameless_checkbox = QCheckBox(
            "Frameless window"
        )
        self.frameless_checkbox.setChecked(
            bool(frameless_window)
        )
        self.frameless_checkbox.setToolTip(
            wrapped_tooltip(
                "Frameless window\n"
                "When enabled, removes the window frame and title bar."
            )
        )
        self.frameless_checkbox.stateChanged.connect(
            self.main_window.set_frameless_window_preference
        )

        self.current_rnd_checkbox = QCheckBox(
            "Show current RND value"
        )
        self.current_rnd_checkbox.setChecked(
            self.show_current_rnd_value
        )
        self.current_rnd_checkbox.setToolTip(
            wrapped_tooltip(
                "Show current RND value\n"
                "Displays the last generated "
                "RND value in a large font."
            )
        )
        self.current_rnd_checkbox.stateChanged.connect(
            self.main_window.set_show_current_rnd_value
        )

        rnd_value_size_row = QHBoxLayout()
        rnd_value_size_row.setContentsMargins(0, 0, 0, 0)
        rnd_value_size_row.setSpacing(6)
        rnd_value_size_row.addWidget(QLabel("RND Value Size:"))
        self.rnd_value_size_spin = QSpinBox()
        self.rnd_value_size_spin.setRange(10, 100)
        self.rnd_value_size_spin.setValue(self.rnd_value_size)
        self.rnd_value_size_spin.setSuffix(" %")
        self.rnd_value_size_spin.setMaximumWidth(100)
        self.rnd_value_size_spin.setToolTip(
            wrapped_tooltip(
                "RND Value Size\n"
                "The size of the current RND value on the graph "
                "as a percentage of the graph height.\n"
                f"Default: {DEFAULT_RND_VALUE_SIZE}%."
            )
        )
        self.rnd_value_size_spin.valueChanged.connect(
            self.main_window.set_rnd_value_size
        )
        rnd_value_size_row.addWidget(self.rnd_value_size_spin)
        rnd_value_size_row.addStretch()

        self.debug_checkbox = QCheckBox("Debug to terminal")
        self.debug_checkbox.setChecked(bool(debug_to_terminal))
        self.debug_checkbox.toggled.connect(self.main_window.set_debug_to_terminal)
        self.open_debug_terminal_checkbox = QCheckBox("Open terminal for debug output")
        self.open_debug_terminal_checkbox.setChecked(bool(open_terminal_for_debug))
        self.open_debug_terminal_checkbox.toggled.connect(self.main_window.set_open_terminal_for_debug)
        debug_rows_row = QHBoxLayout()
        debug_rows_row.addWidget(QLabel("Main-window debug lines:"))
        self.debug_rows_spin = QSpinBox()
        self.debug_rows_spin.setRange(2, 10)
        self.debug_rows_spin.setValue(max(2, min(10, int(debug_panel_rows))))
        self.debug_rows_spin.valueChanged.connect(self.main_window.set_debug_panel_rows)
        self.debug_rows_spin.setMaximumWidth(78)
        debug_rows_row.addWidget(self.debug_rows_spin)
        debug_rows_row.addStretch(1)

        self.reset_all_button = QPushButton("Reset to Display default")
        self.reset_all_button.setMaximumWidth(150)
        self.reset_all_button.clicked.connect(
            self.main_window.reset_all_preferences
        )

        def make_color_item(
            label,
            attr_name,
            value,
            handler,
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)

            text_label = QLabel(label)
            text_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            color_button = QPushButton()
            color_button.setFixedSize(28, 22)
            color_button.setToolTip(
                wrapped_tooltip(
                    f"{label}: {value.upper()}\n"
                    "Click the square to change this colour."
                )
            )
            color_button.clicked.connect(handler)
            self.set_color_button(
                color_button,
                label,
                value,
            )

            setattr(self, attr_name, color_button)
            row.addWidget(text_label)
            row.addWidget(color_button, 0, Qt.AlignmentFlag.AlignRight)
            return row

        def add_color_group(parent_layout, title_text, items):
            title_label = QLabel(title_text)
            title_label.setStyleSheet(
                "font-weight: bold; padding-top: 2px;"
            )
            parent_layout.addWidget(title_label)
            for item in items:
                parent_layout.addLayout(item)

        # The non-color Display controls stay at the very top in two
        # compact columns to reduce the vertical footprint.
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(3)

        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Color Collection:"))
        self.color_collection_combo = QComboBox()
        self.color_collection_combo.addItems(("Default", "Matrix", "Zombie", "Vampire", "Barbie", "Custom"))
        saved_collection = getattr(self.main_window, "color_collection", "Default")
        saved_index = self.color_collection_combo.findText(saved_collection)
        self.color_collection_combo.setCurrentIndex(max(0, saved_index))
        self.color_collection_combo.currentTextChanged.connect(self.main_window.apply_color_collection)
        palette_row.addWidget(self.color_collection_combo)
        palette_row.addStretch(1)
        layout.addLayout(palette_row)

        settings_columns = QHBoxLayout()
        settings_columns.setContentsMargins(0, 0, 0, 0)
        settings_columns.setSpacing(18)

        left_settings = QVBoxLayout()
        left_settings.setContentsMargins(0, 0, 0, 0)
        left_settings.setSpacing(8)
        left_settings.addLayout(width_row)
        left_settings.addLayout(beats_row)
        left_settings.addWidget(self.reset_graph_checkbox)
        left_settings.addWidget(self.frameless_checkbox)
        left_settings.addStretch()

        right_settings = QVBoxLayout()
        right_settings.setContentsMargins(0, 0, 0, 0)
        right_settings.setSpacing(8)
        right_settings.addWidget(self.current_rnd_checkbox)
        right_settings.addLayout(rnd_value_size_row)
        right_settings.addWidget(self.debug_checkbox)
        right_settings.addWidget(self.open_debug_terminal_checkbox)
        right_settings.addLayout(debug_rows_row)
        right_settings.addStretch()

        settings_columns.addLayout(left_settings, 1)
        settings_columns.addLayout(right_settings, 1)
        layout.addLayout(settings_columns)
        layout.addSpacing(4)

        # Compact two-column color layout. The split keeps the logically
        # related controls together while avoiding a very tall single list.
        color_columns = QHBoxLayout()
        color_columns.setContentsMargins(0, 0, 0, 0)
        color_columns.setSpacing(18)

        left_colors = QVBoxLayout()
        left_colors.setContentsMargins(0, 0, 0, 0)
        left_colors.setSpacing(5)

        right_colors = QVBoxLayout()
        right_colors.setContentsMargins(0, 0, 0, 0)
        right_colors.setSpacing(5)

        def add_color_group(parent_layout, title_text, rows):
            title_label = QLabel(title_text)
            title_label.setStyleSheet(
                "font-weight: bold; padding-top: 2px;"
            )
            parent_layout.addWidget(title_label)
            for row in rows:
                parent_layout.addLayout(row)

        # Left: window / application controls.
        add_color_group(
            left_colors,
            "Window",
            [
                make_color_item(
                    "Background",
                    "background_button",
                    background_color,
                    self.choose_background_color,
                ),
                make_color_item(
                    "Text Background",
                    "window_text_background_button",
                    window_text_background_color,
                    self.choose_window_text_background_color,
                ),
                make_color_item(
                    "Text",
                    "window_text_button",
                    window_text_color,
                    self.choose_window_text_color,
                ),
                make_color_item(
                    "Pot Value Text",
                    "pot_value_text_button",
                    pot_value_text_color,
                    self.choose_pot_value_text_color,
                ),
                make_color_item(
                    "Pot Caption Text",
                    "pot_caption_text_button",
                    pot_caption_text_color,
                    self.choose_pot_caption_text_color,
                ),
                make_color_item(
                    "Range Text",
                    "range_text_button",
                    range_text_color,
                    self.choose_range_text_color,
                ),
            ],
        )
        add_color_group(
            left_colors,
            "Buttons",
            [
                make_color_item(
                    "Background",
                    "button_background_button",
                    button_background_color,
                    self.choose_button_background_color,
                ),
                make_color_item(
                    "Text",
                    "button_text_button",
                    button_text_color,
                    self.choose_button_text_color,
                ),
                make_color_item(
                    "Arrow Background",
                    "arrow_background_button",
                    arrow_background_color,
                    self.choose_arrow_background_color,
                ),
                make_color_item(
                    "Arrow Text",
                    "arrow_text_button",
                    arrow_text_color,
                    self.choose_arrow_text_color,
                ),
            ],
        )
        left_colors.addStretch()

        # Right: graph-specific controls.
        add_color_group(
            right_colors,
            "Main Graph",
            [
                make_color_item(
                    "Background",
                    "graph_background_button",
                    graph_background_color,
                    self.choose_graph_background_color,
                ),
                make_color_item(
                    "Grid",
                    "graph_grid_button",
                    graph_grid_color,
                    self.choose_graph_grid_color,
                ),
                make_color_item(
                    "Axis",
                    "graph_axis_button",
                    graph_axis_color,
                    self.choose_graph_axis_color,
                ),
                make_color_item(
                    "Text",
                    "graph_text_button",
                    graph_text_color,
                    self.choose_graph_text_color,
                ),
                make_color_item(
                    "Points",
                    "graph_point_button",
                    graph_point_color,
                    self.choose_graph_point_color,
                ),
                make_color_item(
                    "RND Value",
                    "rnd_value_button",
                    rnd_value_color,
                    self.choose_rnd_value_color,
                ),
            ],
        )
        add_color_group(
            right_colors,
            "Distribution Preview",
            [
                make_color_item(
                    "Background",
                    "distribution_graph_background_button",
                    distribution_graph_background_color,
                    self.choose_distribution_graph_background_color,
                ),
                make_color_item(
                    "Graph",
                    "distribution_graph_text_button",
                    distribution_graph_text_color,
                    self.choose_distribution_graph_text_color,
                ),
            ],
        )
        add_color_group(
            right_colors,
            "Dropdown",
            [
                make_color_item(
                    "Background",
                    "combo_background_button",
                    combo_background_color,
                    self.choose_combo_background_color,
                ),
                make_color_item(
                    "Text",
                    "combo_text_button",
                    combo_text_color,
                    self.choose_combo_text_color,
                ),
            ],
        )
        right_colors.addStretch()

        color_columns.addLayout(left_colors, 1)
        color_columns.addLayout(right_colors, 1)
        layout.addLayout(color_columns)
        layout.addStretch()

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)
        bottom_row.addWidget(self.reset_all_button)
        bottom_row.addStretch()

        display_help = QPushButton("?")
        display_help.setMaximumWidth(28)
        display_help.clicked.connect(self.show_local_help)
        display_help.setToolTip("Local help")
        bottom_row.addWidget(display_help)
        layout.addLayout(bottom_row)
        layout.addStretch()

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)
        bottom_row.addWidget(self.reset_all_button)
        bottom_row.addStretch()

        display_help = QPushButton("?")
        display_help.setMaximumWidth(28)
        display_help.clicked.connect(self.show_local_help)
        display_help.setToolTip("Local help")
        bottom_row.addWidget(display_help)
        layout.addLayout(bottom_row)

    def set_color_button(self, button, label, color_name):
        color = QColor(color_name)
        if not color.isValid():
            color = QColor("#ffffff")
        foreground = (
            "#ffffff"
            if color.lightnessF() < 0.5
            else "#000000"
        )
        button.setText("")
        button.setAccessibleName(label)
        button.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {color.name()};"
            f"color: {foreground};"
            "border: 1px solid #666666;"
            "border-radius: 2px;"
            "}"
        )

    def choose_background_color(self):
        color = QColorDialog.getColor(
            QColor(self.main_window.background_color),
            self,
            "Select Background Color",
        )
        if color.isValid():
            self.set_color_button(
                self.background_button,
                "Background Color",
                color.name(),
            )
            self.main_window.set_background_color(
                color.name()
            )

    def choose_button_background_color(self):
        self.choose_popup_color(
            "button_background_color",
            self.button_background_button,
            "Button Background Color",
            "Select Button Background Color",
        )

    def choose_button_text_color(self):
        self.choose_popup_color(
            "button_text_color",
            self.button_text_button,
            "Button Text Color",
            "Select Button Text Color",
        )

    def choose_combo_background_color(self):
        self.choose_combo_color(
            "combo_background_color",
            self.combo_background_button,
            "Dropdown Background Color",
            "Select Dropdown Background Color",
        )

    def choose_combo_text_color(self):
        self.choose_combo_color(
            "combo_text_color",
            self.combo_text_button,
            "Dropdown Text Color",
            "Select Dropdown Text Color",
        )

    def choose_combo_color(
        self,
        attribute_name,
        button,
        label,
        dialog_title,
    ):
        current = getattr(
            self.main_window,
            attribute_name,
            "#ffffff",
        )
        color = QColorDialog.getColor(
            QColor(current),
            self,
            dialog_title,
        )
        if not color.isValid():
            return

        color_name = color.name()
        self.set_color_button(
            button,
            label,
            color_name,
        )
        self.main_window.set_combo_color(
            attribute_name,
            color_name,
        )

    def choose_graph_background_color(self):
        self.choose_popup_color(
            "graph_background_color",
            self.graph_background_button,
            "Graph Background Color",
            "Select Graph Background Color",
        )

    def choose_graph_grid_color(self):
        self.choose_popup_color(
            "graph_grid_color",
            self.graph_grid_button,
            "Graph Grid Color",
            "Select Graph Grid Color",
        )

    def choose_graph_axis_color(self):
        self.choose_popup_color(
            "graph_axis_color",
            self.graph_axis_button,
            "Graph Axis Color",
            "Select Graph Axis Color",
        )

    def choose_graph_text_color(self):
        self.choose_popup_color(
            "graph_text_color",
            self.graph_text_button,
            "Graph Text Color",
            "Select Graph Text Color",
        )

    def choose_rnd_value_color(self):
        self.choose_popup_color(
            "rnd_value_color",
            self.rnd_value_button,
            "RND Value Color",
            "Select RND Value Color",
        )

    def choose_graph_point_color(self):
        self.choose_popup_color(
            "graph_point_color",
            self.graph_point_button,
            "Graph Point Color",
            "Select Graph Point Color",
        )

    def choose_window_text_background_color(self):
        self.choose_popup_color(
            "window_text_background_color",
            self.window_text_background_button,
            "Window Text Background Color",
            "Select Window Text Background Color",
        )

    def choose_window_text_color(self):
        self.choose_popup_color(
            "window_text_color",
            self.window_text_button,
            "Window Text Color",
            "Select Window Text Color",
        )

    def choose_pot_value_text_color(self):
        self.choose_popup_color(
            "pot_value_text_color",
            self.pot_value_text_button,
            "Pot Value Text Color",
            "Select Pot Value Text Color",
        )

    def choose_pot_caption_text_color(self):
        self.choose_popup_color(
            "pot_caption_text_color",
            self.pot_caption_text_button,
            "Pot Caption Text Color",
            "Select Pot Caption Text Color",
        )

    def choose_range_text_color(self):
        self.choose_popup_color(
            "range_text_color",
            self.range_text_button,
            "Range Text Color",
            "Select Range Text Color",
        )

    def choose_arrow_background_color(self):
        self.choose_popup_color(
            "arrow_background_color",
            self.arrow_background_button,
            "Arrow Background Color",
            "Select Arrow Background Color",
        )

    def choose_arrow_text_color(self):
        self.choose_popup_color(
            "arrow_text_color",
            self.arrow_text_button,
            "Arrow Text Color",
            "Select Arrow Text Color",
        )

    def choose_distribution_graph_background_color(self):
        self.choose_popup_color(
            "distribution_graph_background_color",
            self.distribution_graph_background_button,
            "Distribution Graph Background Color",
            "Select Distribution Graph Background Color",
        )

    def choose_distribution_graph_text_color(self):
        self.choose_popup_color(
            "distribution_graph_text_color",
            self.distribution_graph_text_button,
            "Distribution Graph Text Color",
            "Select Distribution Graph Text Color",
        )

    def choose_popup_color(
        self,
        attribute_name,
        button,
        label,
        dialog_title,
    ):
        current = getattr(
            self.main_window,
            attribute_name,
            "#ffffff",
        )
        color = QColorDialog.getColor(
            QColor(current),
            self,
            dialog_title,
        )
        if not color.isValid():
            return

        color_name = color.name()
        self.set_color_button(
            button,
            label,
            color_name,
        )
        if attribute_name.startswith("window_text_"):
            self.main_window.set_window_text_color(
                attribute_name,
                color_name,
            )
        elif attribute_name.startswith("pot_"):
            self.main_window.set_pot_text_color(
                attribute_name,
                color_name,
            )
        elif attribute_name == "range_text_color":
            self.main_window.set_range_text_color(
                color_name,
            )
        elif attribute_name.startswith("arrow_"):
            self.main_window.set_arrow_color(
                attribute_name,
                color_name,
            )
        elif attribute_name.startswith("distribution_graph_"):
            self.main_window.set_distribution_graph_color(
                attribute_name,
                color_name,
            )
        elif attribute_name == "rnd_value_color":
            self.main_window.set_rnd_value_color(color_name)
        else:
            self.main_window.set_button_color(
                attribute_name,
                color_name,
            )

    def show_local_help(self):
        QMessageBox.information(
            self,
            "Display Help",
            "Display settings\n\n"
            "Configure the window size, colours, left-click graph behaviour, "
            "frameless mode, display colours, and terminal debug output.\n\n"
            "Frameless window removes the window frame and title bar.\n\n"
            "Click the small square beside a colour name to change "
            "that colour.\n\n"
            "Reset to Display default restores the Display settings "
            "to their default values."
        )

    def values(self):
        return (
            self.width_spin.value(),
            self.main_window.background_color,
            self.main_window.button_background_color,
            self.main_window.button_text_color,
            self.main_window.combo_background_color,
            self.main_window.combo_text_color,
            self.main_window.graph_background_color,
            self.main_window.graph_text_color,
            self.main_window.graph_grid_color,
            self.main_window.graph_axis_color,
            self.main_window.graph_point_color,
            self.main_window.window_text_background_color,
            self.main_window.window_text_color,
            self.main_window.pot_value_text_color,
            self.main_window.pot_caption_text_color,
            self.main_window.range_text_color,
            self.main_window.arrow_background_color,
            self.main_window.arrow_text_color,
            self.main_window.distribution_graph_background_color,
            self.main_window.distribution_graph_text_color,
            self.reset_graph_checkbox.isChecked(),
            self.debug_checkbox.isChecked(),
            self.graph_beats_spin.value(),
            self.frameless_checkbox.isChecked(),
            self.main_window.show_current_rnd_value,
            self.main_window.rnd_value_color,
            self.main_window.rnd_value_size,
        )


class AspectRatioImageLabel(QLabel):
    """Image area that always paints the largest possible square indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMinimumSize(1, 1)

    def set_source_pixmap(self, pixmap):
        self._source_pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self._source_pixmap.isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )

        side = min(self.width(), self.height())
        if side <= 0:
            return

        scaled = self._source_pixmap.scaled(
            QSize(side, side),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class MidiNumberWidget(QWidget):
    """One MIDI channel numeric display."""

    def __init__(self, channel, parent=None):
        super().__init__(parent)

        self.channel = channel
        self.midi_value = None
        self.midi_active = False

        self.value_label = QLabel("—", self)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.channel_label = QLabel(
            f"CH {self.channel + 1}",
            self,
        )
        self.channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label.setStyleSheet("font-weight: bold;")
        self.channel_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.active_status_label = QLabel(self)
        self.active_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.active_status_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.value_label, 1)
        layout.addWidget(self.channel_label, 0)

        self.update_value_font()

    def update_value_font(self):
        side = min(self.width(), self.height())
        if side <= 0:
            return

        pixel_size = max(12, min(160, int(round(side * 0.28))))

        font = self.value_label.font()
        font.setPixelSize(pixel_size)
        font.setBold(True)
        self.value_label.setFont(font)

        label_height = max(16, int(round(pixel_size * 0.75)))
        self.channel_label.setFixedHeight(label_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_value_font()
        QTimer.singleShot(0, self.update_active_status)

    def set_value(self, value):
        self.midi_value = int(value)
        self.value_label.setText(str(self.midi_value))
        self.update_value_font()

    def set_midi_activity(self, active):
        self.midi_active = bool(active)
        self.update_active_status()

    def update_active_status(self):
        if (
            not self.midi_active
            or not self.window().show_active_status
        ):
            self.active_status_label.hide()
            return

        template = self.window().active_status_text
        text = template.replace(
            "{channel}",
            str(self.channel + 1),
        )

        foreground = self.window().active_text_color
        background = self.window().active_background_color
        border = self.window().active_text_color

        self.active_status_label.setText(text)
        self.active_status_label.setStyleSheet(
            f"QLabel {{"
            f"color: {foreground};"
            f"background-color: {background};"
            f"border: 1px solid {border};"
            "padding: 4px 8px;"
            "font-family: Arial;"
            "font-weight: bold;"
            "}"
        )

        available_width = max(1, self.width() - 4)
        font = self.active_status_label.font()
        font.setFamily("Arial")
        font.setBold(True)

        configured_width = max(1, self.window().width())
        target_pixel_size = max(
            6,
            min(24, int(round(configured_width * 0.040))),
        )

        for pixel_size in range(target_pixel_size, 5, -1):
            font.setPixelSize(pixel_size)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            if text_width + 18 <= available_width:
                break

        self.active_status_label.setFont(font)
        label_width = min(
            available_width,
            max(1, QFontMetrics(font).horizontalAdvance(text) + 18),
        )
        self.active_status_label.setFixedWidth(label_width)
        self.active_status_label.adjustSize()
        self.active_status_label.setFixedWidth(label_width)

        value_rect = self.value_label.geometry()
        x = max(0, (self.width() - label_width) // 2)
        y = max(
            0,
            value_rect.bottom()
            - self.active_status_label.height()
            - 4,
        )

        self.active_status_label.move(x, y)
        self.active_status_label.show()
        self.active_status_label.raise_()

    def contextMenuEvent(self, event):
        self.window().show_channel_context_menu(
            self.channel,
            event.globalPos(),
        )
        event.accept()


class MidiChannelWidget(QWidget):
    """One MIDI channel activity indicator."""

    def __init__(self, channel, parent=None):
        super().__init__(parent)

        self.channel = channel
        self.midi_active = False
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.original_on = QPixmap(str(IMAGE_ON))
        self.original_off = QPixmap(str(IMAGE_OFF))

        self.image_label = AspectRatioImageLabel(self)
        self.image_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.channel_label = QLabel(
            f"CH {self.channel + 1}",
            self,
        )
        self.channel_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.channel_label.setStyleSheet(
            "font-weight: bold;"
        )
        self.channel_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.active_status_label = QLabel(self)
        self.active_status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.active_status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.active_status_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.channel_label, 0)

        self.update_channel_label_size()
        self.update_image()

    def update_channel_label_size(self):
        # Base the text size on the actual rendered LED square, not on the
        # whole cell. This makes the relationship visible when the LED grows.
        led_side = min(
            self.image_label.width(),
            self.image_label.height(),
        )
        if led_side <= 0:
            return

        # The CH text scales directly with the rendered LED diameter.
        # 12 px text for a 60 px LED is the reference proportion.
        # Therefore a 120 px LED gets 24 px text, a 30 px LED gets 6 px,
        # subject only to a small readability floor.
        pixel_size = int(round(led_side * 0.20))
        pixel_size = max(6, min(96, pixel_size))

        font = self.channel_label.font()
        font.setPixelSize(pixel_size)
        font.setBold(True)
        self.channel_label.setFont(font)

        label_height = max(16, int(round(pixel_size * 1.35)))
        self.channel_label.setFixedHeight(label_height)

    def _deferred_label_resize(self):
        self.update_channel_label_size()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # The grid may finish laying out image_label after this widget's
        # resizeEvent. Update once more on the next event-loop pass so the
        # font follows the final LED size.
        self.update_channel_label_size()
        QTimer.singleShot(
            0,
            self._deferred_label_resize,
        )
        QTimer.singleShot(
            0,
            self.resize_active_status,
        )

    def update_image(self):
        source = (
            self.original_on
            if self.midi_active
            else self.original_off
        )

        if source.isNull():
            self.image_label.clear()
            return

        self.image_label.set_source_pixmap(source)


    def update_active_status(self):
        if (
            not self.midi_active
            or not self.window().show_active_status
        ):
            self.active_status_label.hide()
            return

        template = self.window().active_status_text
        text = template.replace(
            "{channel}",
            str(self.channel + 1),
        )
        foreground = self.window().active_text_color
        background = self.window().active_background_color
        border = self.window().active_text_color

        self.active_status_label.setText(text)
        self.active_status_label.setStyleSheet(
            f"QLabel {{"
            f"color: {foreground};"
            f"background-color: {background};"
            f"border: 1px solid {border};"
            "padding: 4px 8px;"
            "font-family: Arial;"
            "font-weight: bold;"
            "}"
        )

        # The status is an overlay inside the channel cell. Scale its font
        # down when the cell is narrow so the complete message is always
        # visible instead of being clipped at the cell edge.
        available_width = max(1, self.width() - 4)
        font = self.active_status_label.font()
        font.setFamily("Arial")
        font.setBold(True)

        # Scale the popup's CH text from the main window's configured
        # Window Width. This is the same sizing value used for the popup
        # geometry, so the text grows/shrinks with that setting instead of
        # being tied to the LED cell's short dimension.
        configured_width = max(
            1,
            self.window().width(),
        )
        target_pixel_size = max(
            6,
            min(24, int(round(configured_width * 0.040))),
        )

        for pixel_size in range(target_pixel_size, 5, -1):
            font.setPixelSize(pixel_size)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            if text_width + 18 <= available_width:
                break
        else:
            font.setPixelSize(6)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)

        # The box width follows the actual rendered font width plus the
        # horizontal padding. It is not a fixed-size text box. The only
        # constraint is the channel cell itself, so long labels remain
        # completely inside narrow layouts.
        self.active_status_label.setFont(font)
        label_width = min(
            available_width,
            max(1, text_width + 18),
        )
        self.active_status_label.setFixedWidth(label_width)
        self.active_status_label.adjustSize()
        self.active_status_label.setFixedWidth(label_width)

        # Keep the complete status inside this channel widget. It is an
        # overlay, so it does not alter the grid geometry or LED sizing.
        image_rect = self.image_label.geometry()
        x = max(
            0,
            (self.width() - label_width) // 2,
        )
        y = max(
            0,
            image_rect.bottom()
            - self.active_status_label.height()
            - 4,
        )
        self.active_status_label.move(x, y)
        self.active_status_label.show()
        self.active_status_label.raise_()

    def resize_active_status(self):
        if self.midi_active:
            self.update_active_status()

    def set_midi_activity(self, active):
        self.midi_active = bool(active)
        self.update_image()
        self.update_active_status()
        self.update_active_status()

    def contextMenuEvent(self, event):
        self.window().show_channel_context_menu(
            self.channel,
            event.globalPos(),
        )
        event.accept()


class RandomizerGraphWidget(QWidget):
    """Live MIDI randomizer graph shown in the main application window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.background_color = DEFAULT_GRAPH_BACKGROUND
        self.grid_color = DEFAULT_GRAPH_GRID_COLOR
        self.axis_color = DEFAULT_GRAPH_AXIS_COLOR
        self.text_color = DEFAULT_GRAPH_TEXT_COLOR
        self.point_color = DEFAULT_GRAPH_POINT_COLOR
        self.rnd_value_color = DEFAULT_RND_VALUE_COLOR
        self.rnd_value_size = DEFAULT_RND_VALUE_SIZE
        self.show_current_rnd_value = DEFAULT_SHOW_CURRENT_RND_VALUE
        self.current_rnd_value = None
        self.max_points = DEFAULT_GRAPH_BEATS
        self.reset_on_left_click = True
        self.setMinimumSize(80, 60)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_colors(self, background=None, grid=None, axis=None, text=None, point=None):
        for value, attr in (
            (background, "background_color"),
            (grid, "grid_color"),
            (axis, "axis_color"),
            (text, "text_color"),
            (point, "point_color"),
        ):
            if value is not None:
                color = QColor(value)
                if color.isValid():
                    setattr(self, attr, color.name())
        self.update()

    def set_rnd_value_color(self, color):
        color = QColor(color)
        if color.isValid():
            self.rnd_value_color = color.name()
            self.update()

    def set_rnd_value_size(self, size):
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = DEFAULT_RND_VALUE_SIZE
        self.rnd_value_size = max(10, min(100, size))
        self.update()

    def set_show_current_rnd_value(self, enabled):
        self.show_current_rnd_value = bool(enabled)
        self.update()

    def set_current_rnd_value(self, value):
        try:
            value = max(MIDI_MIN, min(MIDI_MAX, int(value)))
        except (TypeError, ValueError):
            return
        self.current_rnd_value = value
        self.update()

    def set_max_points(self, count):
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = DEFAULT_GRAPH_BEATS

        count = max(1, min(GRAPH_MAX_POINTS, count))
        self.max_points = count
        if len(self.values) > count:
            self.values = self.values[-count:]
        self.update()

    def add_value(self, value):
        try:
            value = max(MIDI_MIN, min(MIDI_MAX, int(value)))
        except (TypeError, ValueError):
            return
        self.values.append(value)
        self.current_rnd_value = value
        if len(self.values) > self.max_points:
            self.values = self.values[-self.max_points:]
        self.update()

    def clear_values(self):
        self.values.clear()
        self.update()

    def set_reset_on_left_click(self, enabled):
        self.reset_on_left_click = bool(enabled)

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.reset_on_left_click
        ):
            self.clear_values()
            event.accept()
            return
        super().mousePressEvent(event)

    @staticmethod
    def _x_for_index(plot, index, count):
        if count <= 1:
            return plot.center().x()
        return plot.left() + index * plot.width() / float(count - 1)

    @staticmethod
    def _y_for_value(plot, value):
        ratio = max(0.0, min(1.0, value / float(MIDI_MAX)))
        return plot.bottom() - ratio * plot.height()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = self.rect().adjusted(4, 4, -4, -4)
        painter.setPen(QColor(self.grid_color))
        painter.setBrush(QColor(self.background_color))
        painter.drawRoundedRect(outer, 7, 7)

        left = outer.left() + 38
        top = outer.top() + 16
        right = outer.right() - 14

        # Keep the visual gap between the plot and the "beats" caption
        # proportional to the window width, but only mildly. The previous
        # rule scaled the whole bottom margin and therefore made the gap
        # grow too aggressively. Here we calculate the actual optical gap
        # independently from the caption baseline.
        compact_beats = self.width() < 280
        if compact_beats:
            bottom_margin = 12
            caption_baseline_offset = 0
        else:
            width_delta = max(0, self.width() - 280)
            caption_gap = 12.0 + width_delta * 0.035
            caption_gap = max(12.0, min(28.0, caption_gap))

            width_scale = self.width() / 290.0
            caption_baseline_offset = max(
                10,
                min(18, int(round(13.0 * width_scale))),
            )
            bottom_margin = int(
                round(caption_gap + caption_baseline_offset)
            )

        bottom = outer.bottom() - bottom_margin
        if right <= left or bottom <= top:
            painter.end()
            return

        plot = outer.__class__(left, top, right - left, bottom - top)

        # MIDI velocity scale is fixed at 0..127.
        painter.setPen(QColor(self.grid_color))
        for value in (127, 64, 0):
            y = self._y_for_value(plot, value)
            painter.drawLine(plot.left(), y, plot.right(), y)

        # Beat grid; deliberately no numeric X-axis labels.
        count = len(self.values)
        if count > 1:
            for index in range(count):
                x = self._x_for_index(plot, index, count)
                painter.drawLine(x, plot.top(), x, plot.bottom())
        elif count == 1:
            x = plot.center().x()
            painter.drawLine(x, plot.top(), x, plot.bottom())

        painter.setPen(QColor(self.axis_color))
        painter.drawLine(plot.left(), plot.top(), plot.left(), plot.bottom())
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())

        # Small beat ticks, but no numeric beat labels.
        if count > 0:
            for index in range(count):
                x = self._x_for_index(plot, index, count)
                painter.drawLine(x, plot.bottom(), x, plot.bottom() + 6)

        # Y-axis labels only.
        painter.setPen(QColor(self.text_color))
        font = painter.font()
        font.setPixelSize(max(9, min(18, int(self.height() * 0.055))))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        for value in (127, 64, 0):
            y = self._y_for_value(plot, value)
            label = str(value)
            painter.drawText(
                plot.left() - metrics.horizontalAdvance(label) - 8,
                y + metrics.ascent() // 2,
                label,
            )

        if self.values:
            count = len(self.values)
            radius = max(
                1.5,
                min(
                    8.0,
                    min(plot.width(), plot.height()) * 0.018,
                ),
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.point_color))
            for index, value in enumerate(self.values):
                x = self._x_for_index(plot, index, count)
                y = self._y_for_value(plot, value)
                painter.drawEllipse(
                    int(round(x - radius)),
                    int(round(y - radius)),
                    int(round(radius * 2)),
                    int(round(radius * 2)),
                )

        if (
            self.show_current_rnd_value
            and self.current_rnd_value is not None
        ):
            rnd_font = painter.font()
            rnd_font.setBold(True)
            rnd_font.setPixelSize(
                max(
                    18,
                    min(
                        180,
                        int(
                            round(
                                self.height()
                                * (self.rnd_value_size / 100.0)
                            )
                        ),
                    ),
                )
            )
            painter.setFont(rnd_font)
            painter.setPen(QColor(self.rnd_value_color))
            rnd_text = str(self.current_rnd_value)
            painter.drawText(
                plot,
                Qt.AlignmentFlag.AlignCenter,
                rnd_text,
            )

        # X-axis title: only "beats". Hide it in the compact layout.
        if not compact_beats:
            painter.setPen(QColor(self.text_color))
            beat_font = painter.font()
            beat_font.setPixelSize(max(10, min(20, int(self.height() * 0.065))))
            painter.setFont(beat_font)
            beat_metrics = painter.fontMetrics()
            beat_text = "beats"
            painter.drawText(
                plot.center().x() - beat_metrics.horizontalAdvance(beat_text) // 2,
                outer.bottom() - caption_baseline_offset,
                beat_text,
            )

        painter.end()



class VerticalRotaryDial(QDial):
    """QDial controlled by vertical mouse movement and the mouse wheel.

    The visual marker is a simple black radial line instead of the
    platform-dependent circular marker used by the native QDial.
    """

    doubleClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dragging = False
        self._last_mouse_y = 0.0
        self._drag_remainder = 0.0
        self._double_click_value = 0
        self._visual_center_value = 0
        self._double_click_lock = False
        self._debug_log_callback = None
        self.setNotchesVisible(False)
        self.setWrapping(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def set_double_click_value(self, value):
        self._double_click_value = int(value)

    def set_visual_center_value(self, value):
        self._visual_center_value = int(value)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._double_click_lock:
                event.accept()
                return
            self._dragging = True
            self._last_mouse_y = event.position().y()
            self._drag_remainder = 0.0
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._double_click_lock:
            event.accept()
            return
        if self._dragging:
            current_y = event.position().y()
            delta_y = self._last_mouse_y - current_y
            self._last_mouse_y = current_y

            # About 80 vertical pixels correspond to the full range.
            # Accumulate fractional movement so small mouse motions are
            # not lost on large ranges.
            self._drag_remainder += delta_y * (
                (self.maximum() - self.minimum()) / 80.0
            )
            steps = int(self._drag_remainder)
            if steps:
                self._drag_remainder -= steps
                self.setValue(
                    max(
                        self.minimum(),
                        min(self.maximum(), self.value() + steps),
                    )
                )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._double_click_lock:
                event.accept()
                return
            if self._dragging:
                self._dragging = False
                self._drag_remainder = 0.0
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._double_click_lock = True
            self._dragging = False
            self._drag_remainder = 0.0
            center_value = int(self._double_click_value)

            # Keep the dial locked through the complete double-click
            # sequence and verify the value after 300 ms.
            self.setValue(center_value)
            self.doubleClicked.emit(center_value)

            def verify_center():
                self._dragging = False
                self._drag_remainder = 0.0
                self.setValue(center_value)
                self.update()
                debug_log = getattr(self, "_debug_log_callback", None)
                if debug_log is not None:
                    debug_log(self.value())

            def unlock():
                self._dragging = False
                self._drag_remainder = 0.0
                self.setValue(center_value)
                self._double_click_lock = False
                debug_log = getattr(self, "_debug_log_callback", None)
                if debug_log is not None:
                    debug_log(self.value())

            QTimer.singleShot(300, verify_center)
            QTimer.singleShot(320, unlock)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            steps = int(delta / 120)
            if steps:
                self.setValue(
                    max(
                        self.minimum(),
                        min(self.maximum(), self.value() + steps),
                    )
                )
            event.accept()
            return
        event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        side = min(self.width(), self.height())
        if side <= 2:
            painter.end()
            return

        center = self.rect().center()
        radius = side / 2.0 - 5.0

        palette = self.palette()
        body = palette.color(QPalette.ColorRole.Button)
        outline = palette.color(QPalette.ColorRole.Mid)

        # Thicker knob outline: 2x the previous stroke.
        painter.setPen(QPen(outline, 3.0))
        painter.setBrush(body)
        painter.drawEllipse(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )

        # Standard QDial sweep: -135° .. +135°.
        minimum = self.minimum()
        maximum = self.maximum()
        value = self.value()
        visual_center = max(
            minimum,
            min(maximum, int(self._visual_center_value)),
        )

        # The semantic neutral value is drawn at exactly 12 o'clock.
        # This changes only the visual mapping; the actual dial value,
        # range, dragging and application logic remain untouched.
        if maximum <= minimum:
            ratio = 0.0
        elif minimum < visual_center < maximum:
            if value <= visual_center:
                ratio = 0.5 * (
                    (value - minimum)
                    / float(visual_center - minimum)
                )
            else:
                ratio = 0.5 + 0.5 * (
                    (value - visual_center)
                    / float(maximum - visual_center)
                )
        else:
            ratio = (
                (value - minimum)
                / float(maximum - minimum)
            )

        ratio = max(0.0, min(1.0, ratio))
        angle = math.radians(225.0 - 270.0 * ratio)

        line_start = max(3.0, radius * 0.10)

        line_length = max(7.0, radius * 0.62)

        x1 = center.x() + math.cos(angle) * (line_start + line_length)

        y1 = center.y() - math.sin(angle) * (line_start + line_length)

        x2 = center.x() + math.cos(angle) * line_start

        y2 = center.y() - math.sin(angle) * line_start

        # Indicator line: same color as the knob outline, 3x thicker.
        painter.setPen(QPen(outline, max(6.0, radius * 0.165)))

        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))


class DistributionMiniPreview(DistributionPreview):
    """Square distribution preview used by the main-window selector."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setFixedSize(82, 82)


class DistributionSelector(QWidget):
    """Compact four-state distribution selector."""

    valueChanged = Signal(int)

    def __init__(self, distribution, bias, caption="Distribution", parent=None):
        super().__init__(parent)

        self._caption = caption
        self._keys = tuple(
            key for key, _label in MidiRandomizer.DISTRIBUTIONS
        )
        self._control_size = 82
        self._compact_labels = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(1)

        # The state label occupies the same vertical position and height
        # as the numeric labels above the ordinary main-window knobs.
        self.state_label = QLabel()
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setMinimumHeight(22)
        self.state_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.state_label)

        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(4)

        self.preview = DistributionMiniPreview(self)
        self.preview.setToolTip(
            wrapped_tooltip(
                "Distribution preview\n"
                "The curve shows the current probability distribution.\n"
                "The preview updates immediately when Bias changes."
            )
        )
        control_row.addWidget(
            self.preview,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        arrow_column = QVBoxLayout()
        arrow_column.setContentsMargins(0, 0, 0, 0)
        arrow_column.setSpacing(2)

        self.previous_button = QPushButton("▲")
        self.next_button = QPushButton("▼")

        self.previous_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.previous_button.setToolTip(
            wrapped_tooltip(
                "Previous distribution\n"
                "Selects the previous distribution: Uniform, Center, Edge, or Gaussian."
            )
        )
        self.next_button.setToolTip(
            wrapped_tooltip(
                "Next distribution\n"
                "Selects the next distribution: Uniform, Center, Edge, or Gaussian."
            )
        )

        self.previous_button.clicked.connect(self.previous)
        self.next_button.clicked.connect(self.next)

        arrow_column.addWidget(self.previous_button)
        arrow_column.addWidget(self.next_button)
        control_row.addLayout(arrow_column)

        layout.addLayout(control_row)

        self.caption_label = QLabel(caption)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.caption_label)

        self.set_distribution(distribution)
        self.set_bias(bias)
        self.set_control_size(self._control_size)

    def _index(self):
        try:
            return self._keys.index(self.preview.distribution)
        except ValueError:
            return 0

    def _set_index(self, index, emit=True):
        index = max(0, min(len(self._keys) - 1, int(index)))
        distribution = self._keys[index]
        changed = distribution != self.preview.distribution

        self.preview.set_distribution(distribution)
        self.state_label.setText(
            self._distribution_label(distribution)
        )

        if emit and changed:
            self.valueChanged.emit(index)

    @staticmethod
    def _long_distribution_label(distribution):
        return {
            "uniform": "UNIFORM",
            "center": "CENTER-BIASED",
            "edge": "EDGE-BIASED",
            "gaussian": "GAUSSIAN",
        }.get(distribution, str(distribution).upper())

    def _distribution_label(self, distribution):
        if self._compact_labels:
            return dict(MidiRandomizer.DISTRIBUTIONS).get(
                distribution, str(distribution).upper()
            )
        return self._long_distribution_label(distribution)

    def set_compact_labels(self, compact):
        self._compact_labels = bool(compact)
        self.state_label.setText(
            self._distribution_label(self.preview.distribution)
        )

    def previous(self):
        self._set_index(self._index() - 1)

    def next(self):
        self._set_index(self._index() + 1)

    def set_distribution(self, distribution):
        self._set_index(
            self._keys.index(distribution)
            if distribution in self._keys
            else 0,
            emit=False,
        )

    def set_bias(self, bias):
        self.preview.set_bias(bias)

    def distribution(self):
        return self.preview.distribution

    def value(self):
        return self._index()

    def set_display_colors(
        self,
        value_text_color,
        caption_text_color,
        background_color=None,
    ):
        value_color = QColor(value_text_color)
        caption_color = QColor(caption_text_color)
        background = QColor(
            background_color
            if background_color is not None
            else "#000000"
        )
        if not value_color.isValid():
            value_color = QColor("#000000")
        if not caption_color.isValid():
            caption_color = QColor("#000000")
        if not background.isValid():
            background = QColor("#ffffff")

        self.state_label.setStyleSheet(
            f"background-color: {background.name()};"
            f"color: {value_color.name()};"
            "font-weight: bold;"
            "padding: 1px 5px;"
            "border-radius: 3px;"
        )
        self.caption_label.setStyleSheet(
            f"color: {caption_color.name()};"
            "font-weight: bold;"
        )

    def set_arrow_style(self, background, text_color):
        stylesheet = (
            "QPushButton {"
            f"background-color: {background};"
            f"color: {text_color};"
            "}"
        )
        self.previous_button.setStyleSheet(stylesheet)
        self.next_button.setStyleSheet(stylesheet)

    def set_graph_colors(self, background, text_color):
        self.preview.set_colors(
            background=background,
            text=text_color,
        )

    def set_control_size(self, size):
        size = max(44, min(140, int(size)))
        self._control_size = size

        # The graph is exactly the same diameter as the main rotary knobs.
        self.preview.setFixedSize(size, size)

        # Each arrow button is about 40% of the graph width. Two compact
        # buttons are stacked to the left/right without changing the
        # selector's vertical footprint.
        button_width = max(18, int(round(size * 0.40)))
        button_height = max(17, int(round(size * 0.40)))

        for button in (self.previous_button, self.next_button):
            button.setFixedSize(button_width, button_height)

        self.setMinimumWidth(
            size + button_width + 8
        )


class MainRotaryKnob(QWidget):
    """Compact rotary control used for the main-window custom settings."""

    valueChanged = Signal(int)
    doubleClicked = Signal(int)

    def __init__(
        self,
        minimum,
        maximum,
        value,
        caption,
        formatter,
        parent=None,
        double_click_value=None,
    ):
        super().__init__(parent)
        self._formatter = formatter
        self._caption = caption
        self._double_click_value = int(
            round((minimum + maximum) / 2.0)
        ) if double_click_value is None else int(double_click_value)
        self._knob_size = 82

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(1)

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setMinimumHeight(22)
        self.value_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.value_label)

        self.dial = VerticalRotaryDial()
        self.dial.setRange(int(minimum), int(maximum))
        self.dial.set_double_click_value(
            self._double_click_value
        )
        self.dial._debug_log_callback = self._debug_log_300ms
        self.dial.setValue(int(value))
        self.dial.setNotchesVisible(False)
        self.dial.setWrapping(False)
        self.dial.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.dial.setToolTip(
            wrapped_tooltip(self._knob_tooltip_text(caption))
        )
        self.dial.valueChanged.connect(self._dial_value_changed)
        self.dial.doubleClicked.connect(self._dial_double_clicked)
        layout.addWidget(self.dial, 0, Qt.AlignmentFlag.AlignHCenter)

        self.caption_label = QLabel(caption)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.caption_label)

        self.set_knob_size(self._knob_size)
        self.set_value(int(value))

    def _knob_tooltip_text(self, caption):
        return {
            "Bias": (
                "Bias\n"
                "Shifts the centre of gravity of the distribution.\n"
                "0 = neutral; negative = lower values; "
                "positive = favours higher values.\n"
                "Does not change the Minimum/Maximum range.\n"
                "Double-click: 0 (centre position)."
            ),
            "Maximum Change": (
                "Maximum Change\n"
                "The new value may differ by at most this amount "
                "from the previously generated value.\n"
                "Example: ±10 allows a maximum deviation of 10 from the previous value. "
                "\n"
                "Double-click: set the knob to its physical midpoint."
            ),
            "Width": (
                "Width\n"
                "For PAN, sets the width of the interval.\n"
                "Mirror behaviour: the range centre remains fixed, "
                "and both sides expand or contract symmetrically.\n"
                "Double-click: set the knob to its physical midpoint."
            ),
            "Position": (
                "Position\n"
                "For Velocity, shifts the interval position "
                "while preserving its width.\n"
                "The range always remains within MIDI values 0–127.\n"
                "Double-click: reset to the midpoint."
            ),
        }.get(caption, str(caption))

    def _debug_log_300ms(self, value):
        callback = getattr(self, "_main_debug_log", None)
        if callback is not None:
            callback(
                f"Double-click 0.3s check → {self._caption} = "
                f"{self._formatter(int(value))}"
            )

    def _dial_double_clicked(self, value):
        self._update_value_label(value)
        self.doubleClicked.emit(int(value))

    def _dial_value_changed(self, value):
        self._update_value_label(value)
        self.valueChanged.emit(int(value))

    def _update_value_label(self, value):
        self.value_label.setText(self._formatter(int(value)))

    def set_value(self, value):
        self.dial.blockSignals(True)
        try:
            self.dial.setValue(int(value))
        finally:
            self.dial.blockSignals(False)
        self._update_value_label(int(value))

    def value(self):
        return int(self.dial.value())

    def set_caption(self, caption):
        self._caption = str(caption)
        self.caption_label.setText(self._caption)
        self.dial.setToolTip(
            wrapped_tooltip(self._knob_tooltip_text(self._caption))
        )

    def set_knob_size(self, size):
        size = max(44, min(140, int(size)))
        self._knob_size = size
        self.dial.setFixedSize(size, size)
        self.setMinimumWidth(size + 12)

    def set_display_colors(
        self,
        value_text_color,
        caption_text_color,
        background_color="#ffffff",
    ):
        value_color = QColor(value_text_color)
        caption_color = QColor(caption_text_color)
        background = QColor(background_color)
        if not value_color.isValid():
            value_color = QColor("#000000")
        if not caption_color.isValid():
            caption_color = QColor("#000000")
        if not background.isValid():
            background = QColor("#ffffff")
        self.value_label.setStyleSheet(
            f"background-color: {background.name()};"
            f"color: {value_color.name()};"
            "font-weight: bold;"
            "padding: 1px 5px;"
            "border-radius: 3px;"
        )
        self.caption_label.setStyleSheet(
            f"color: {caption_color.name()};"
            "font-weight: bold;"
        )


class MidiRandomizeWindow(QMainWindow):
    """Main MIDI Randomize window."""

    def __init__(self, backend=None, frameless=None):
        self._close_confirmed = False
        self._replacing_window = False
        self._frameless = (
            self.load_frameless_window()
            if frameless is None
            else bool(frameless)
        )
        super().__init__()

        if self._frameless:
            self.setWindowFlags(
                self.windowFlags()
                | Qt.WindowType.FramelessWindowHint
            )

        self.setWindowTitle(APP_TITLE)

        self.default_size = DEFAULT_SIZE
        self.window_size = self.load_size()
        self.window_resizable = self.load_resizable()
        self.layout_mode = self.load_layout()
        visibility = self.load_visibility_preferences()
        self.show_graph = visibility["show_graph"]
        self.show_controls = visibility["show_controls"]
        self.show_interval = visibility["show_interval"]
        self.start_in_play = self.load_start_in_play()
        self.window_width = self.load_window_width()
        self.background_color = self.load_background_color()
        self.show_channel_labels = False
        self.show_active_status = False
        self.active_status_text = ""
        self.channel_label_color = "#000000"
        self.active_text_color = self.load_color_preference(
            "active_text_color",
            DEFAULT_WINDOW_TEXT_COLOR,
        )
        self.active_background_color = self.load_color_preference(
            "active_background_color",
            self.background_color,
        )
        self.button_background_color = self.load_color_preference(
            "button_background_color", DEFAULT_BUTTON_BACKGROUND_COLOR
        )
        self.button_text_color = self.load_color_preference(
            "button_text_color", DEFAULT_BUTTON_TEXT_COLOR
        )
        self.combo_background_color = self.load_color_preference(
            "combo_background_color", DEFAULT_COMBO_BACKGROUND_COLOR
        )
        self.combo_text_color = self.load_color_preference(
            "combo_text_color", DEFAULT_COMBO_TEXT_COLOR
        )
        self.window_text_background_color = self.load_color_preference(
            "window_text_background_color",
            DEFAULT_WINDOW_TEXT_BACKGROUND_COLOR,
        )
        self.window_text_color = self.load_color_preference(
            "window_text_color",
            DEFAULT_WINDOW_TEXT_COLOR,
        )
        self.pot_value_text_color = self.load_color_preference(
            "pot_value_text_color",
            DEFAULT_POT_VALUE_TEXT_COLOR,
        )
        self.pot_caption_text_color = self.load_color_preference(
            "pot_caption_text_color",
            DEFAULT_POT_CAPTION_TEXT_COLOR,
        )
        self.range_text_color = self.load_color_preference(
            "range_text_color",
            DEFAULT_RANGE_TEXT_COLOR,
        )
        self.arrow_background_color = self.load_color_preference(
            "arrow_background_color",
            DEFAULT_ARROW_BACKGROUND_COLOR,
        )
        self.arrow_text_color = self.load_color_preference(
            "arrow_text_color",
            DEFAULT_ARROW_TEXT_COLOR,
        )
        self.distribution_graph_background_color = self.load_color_preference(
            "distribution_graph_background_color",
            DEFAULT_DISTRIBUTION_GRAPH_BACKGROUND_COLOR,
        )
        self.distribution_graph_text_color = self.load_color_preference(
            "distribution_graph_text_color",
            DEFAULT_DISTRIBUTION_GRAPH_TEXT_COLOR,
        )
        self.graph_background_color = self.load_color_preference(
            "graph_background_color", DEFAULT_GRAPH_BACKGROUND
        )
        self.graph_grid_color = self.load_color_preference(
            "graph_grid_color", DEFAULT_GRAPH_GRID_COLOR
        )
        self.graph_axis_color = self.load_color_preference(
            "graph_axis_color", DEFAULT_GRAPH_AXIS_COLOR
        )
        self.graph_text_color = self.load_color_preference(
            "graph_text_color", DEFAULT_GRAPH_TEXT_COLOR
        )
        self.graph_point_color = self.load_color_preference(
            "graph_point_color", DEFAULT_GRAPH_POINT_COLOR
        )
        self.reset_graph_on_left_click = self.load_reset_graph_on_left_click()
        self.graph_beats = self.load_graph_beats()
        self.show_current_rnd_value = self.load_show_current_rnd_value()
        self.rnd_value_color = self.load_color_preference(
            "rnd_value_color",
            DEFAULT_RND_VALUE_COLOR,
        )
        self.rnd_value_size = self.load_rnd_value_size()
        self.debug_to_terminal = self.load_debug_to_terminal()
        self.open_terminal_for_debug = self.load_open_terminal_for_debug()
        self.debug_panel_rows = self.load_debug_panel_rows()
        self._debug_messages = []
        self._backend_debug_queue = SimpleQueue()
        self._debug_terminal_process = None
        self._debug_log_file = Path.cwd() / "rnd-pan-debug.log"
        self.color_collection = self.load_color_collection()
        self.load_randomizer_settings()
        self.midi_pan = None
        self._resizing_square = False
        self._resizing_layout = False
        self._auto_layout_resize = False
        self._frameless_drag_start = None
        self._frameless_drag_offset = None
        self._frameless_drag_active = False
        self._frameless_resize_edges = None
        self._frameless_resize_geometry = None
        self._frameless_resize_start = None

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.setMinimumSize(QSize(MIN_SIZE, MIN_SIZE))
        self.setMaximumSize(QSize(MAX_SIZE, MAX_SIZE))

        self.backend = (
            backend
            if backend is not None
            else RndPanBackend(
                debug_to_terminal=self.debug_to_terminal
            )
        )
        if hasattr(self.backend, "set_debug_to_terminal"):
            self.backend.set_debug_to_terminal(
                self.debug_to_terminal
            )
        if hasattr(self.backend, "set_debug_to_terminal"):
            self.backend.set_debug_to_terminal(self.debug_to_terminal)
        self.backend.log_callback = self._queue_backend_debug_message
        self.backend.debug_event_logging = True
        if backend is None:
            self.backend.start()

        # The former 16-channel image grid is replaced by the live
        # MIDI randomizer graph in the main window.  The graph gets a
        # compact control bar underneath it: the Preferences icon, the live preset selector, and the START/STOP control.
        self.channel_widgets = []
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(0)
        self.grid_layout.setVerticalSpacing(0)

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(6, 6, 6, 6)
        central_layout.setSpacing(6)

        graph_container = QWidget(central)
        graph_container.setLayout(self.grid_layout)
        self.graph_container = graph_container
        self._knob_reference_graph_size = None
        self.central_widget = central
        self.setCentralWidget(central)
        self.apply_background_color()

        self.randomizer_graph = RandomizerGraphWidget(graph_container)
        self.randomizer_graph.set_colors(
            self.graph_background_color,
            self.graph_grid_color,
            self.graph_axis_color,
            self.graph_text_color,
            self.graph_point_color,
        )
        if hasattr(self, "main_range_indicator"):
            self.main_range_indicator.set_text_color(self.range_text_color)
        self.randomizer_graph.set_max_points(
            self.graph_beats
        )
        self.randomizer_graph.set_max_points(
            self.graph_beats
        )
        self.randomizer_graph.set_rnd_value_color(
            self.rnd_value_color
        )
        self.randomizer_graph.set_rnd_value_size(
            self.rnd_value_size
        )
        self.randomizer_graph.set_show_current_rnd_value(
            self.show_current_rnd_value
        )
        self.randomizer_graph.set_rnd_value_size(
            self.rnd_value_size
        )
        self.randomizer_graph.set_rnd_value_color(
            self.rnd_value_color
        )
        self.randomizer_graph.set_show_current_rnd_value(
            self.show_current_rnd_value
        )
        self.randomizer_graph.set_reset_on_left_click(
            self.reset_graph_on_left_click
        )
        self.grid_layout.addWidget(self.randomizer_graph, 0, 0)
        central_layout.addWidget(graph_container, 1)

        # Custom randomizer controls live directly below the graph.
        # The numeric value is above each knob; the caption is below it.
        knob_row = QHBoxLayout()
        knob_row.setContentsMargins(0, 0, 0, 0)
        knob_row.setSpacing(6)
        knob_row.addStretch(1)
        self.main_knob_row = knob_row

        self.main_distribution_selector = DistributionSelector(
            randomizer.distribution,
            randomizer.bias,
            "Distribution",
            central,
        )
        self.main_bias_knob = MainRotaryKnob(
            -100,
            100,
            randomizer.bias,
            "Bias",
            lambda value: f"{value:+d}",
            central
        )
        self.main_change_knob = MainRotaryKnob(
            0,
            MIDI_MAX,
            randomizer.max_change,
            "Maximum Change",
            lambda value: "Unlimited" if value >= MIDI_MAX else f"±{value}",
            central
        )
        pan_center = (randomizer.minimum + randomizer.maximum) / 2.0
        pan_half_width = (randomizer.maximum - randomizer.minimum) / 2.0
        pan_max_half_width = max(pan_center, MIDI_MAX - pan_center)
        self.main_interval_knob = MainRotaryKnob(
            -randomizer.minimum,
            MIDI_MAX - randomizer.maximum,
            0,
            "Position",
            lambda value: f"{value:+d}",
            central,
            double_click_value=0,
        )
        initial_center = (randomizer.minimum + randomizer.maximum) / 2.0
        initial_half_width = int(round(
            (randomizer.maximum - randomizer.minimum) / 2.0
        ))
        self.main_width_knob = MainRotaryKnob(
            0,
            max(0, min(int(round(initial_center)), int(round(MIDI_MAX - initial_center)))),
            initial_half_width,
            "Width",
            lambda value: str(int(value)),
            central,
            double_click_value=initial_half_width,
        )
        self.main_bias_knob.dial.set_visual_center_value(0)
        self.main_change_knob.dial.set_visual_center_value(MIDI_MAX // 2)
        self.main_interval_knob.dial.set_visual_center_value(0)
        self.main_interval_knob.dial.setToolTip(
            "Shifts the entire PAN interval without changing its width. "
            "The range always remains within MIDI values 0–127."
        )
        self.main_width_knob.dial.setToolTip(
            "Symmetrically expands or contracts the PAN interval around its centre. "
            "The range always remains within MIDI values 0–127."
        )

        self.main_distribution_selector.valueChanged.connect(
            self.main_distribution_changed
        )
        self.apply_window_text_colors()
        self.apply_arrow_colors()
        self.apply_distribution_graph_colors()

        self.main_bias_knob._main_debug_log = lambda msg: self.debug_log(msg)
        self.main_change_knob._main_debug_log = lambda msg: self.debug_log(msg)
        self.main_interval_knob._main_debug_log = lambda msg: self.debug_log(msg)
        self.main_width_knob._main_debug_log = lambda msg: self.debug_log(msg)

        self.main_bias_knob._main_debug_log = (
            lambda msg: self.debug_log(msg)
        )
        self.main_change_knob._main_debug_log = (
            lambda msg: self.debug_log(msg)
        )
        self.main_interval_knob._main_debug_log = (
            lambda msg: self.debug_log(msg)
        )
        self.main_width_knob._main_debug_log = (
            lambda msg: self.debug_log(msg)
        )

        self.main_bias_knob.doubleClicked.connect(
            self.main_knob_double_clicked
        )
        self.main_change_knob.doubleClicked.connect(
            self.main_knob_double_clicked
        )
        self.main_interval_knob.doubleClicked.connect(
            self.main_knob_double_clicked
        )
        self.main_width_knob.doubleClicked.connect(
            self.main_knob_double_clicked
        )
        self.main_bias_knob.valueChanged.connect(
            self.main_bias_changed
        )
        self.main_change_knob.valueChanged.connect(
            self.main_change_changed
        )
        self.main_interval_knob.valueChanged.connect(
            self.main_interval_changed
        )
        self.main_width_knob.valueChanged.connect(
            self.main_width_changed
        )

        self.main_distribution_selector.set_display_colors(
            self.pot_value_text_color,
            self.pot_caption_text_color,
            self.window_text_background_color,
        )
        knob_row.addWidget(
            self.main_distribution_selector,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        for knob in (
            self.main_bias_knob,
            self.main_change_knob,
            self.main_interval_knob,
            self.main_width_knob,
        ):
            knob.set_display_colors(
                self.pot_value_text_color,
                self.pot_caption_text_color,
                self.window_text_background_color,
            )
            knob_row.addWidget(knob, 0, Qt.AlignmentFlag.AlignCenter)

        knob_row.addStretch(1)
        controls_container = QWidget(central)
        controls_container.setLayout(knob_row)
        self.main_controls_container = controls_container
        central_layout.addWidget(controls_container)

        # Visual range indicator for the active randomization interval.
        # The handles are display-only; the main-window Speed knob remains
        # the control that changes the interval.
        self.main_range_indicator = MainRangeIndicator(0, MIDI_MAX, central)
        self.main_range_indicator.set_text_color(self.range_text_color)
        self.main_range_indicator.rangeChanged.connect(
            self.main_range_indicator_changed
        )
        central_layout.addWidget(self.main_range_indicator)
        self.apply_main_element_visibility()

        # Preferences are loaded before the main controls are created.
        # Synchronize the initial Speed/range display now so the main window
        # starts with the saved custom Minimum/Maximum values.
        self._sync_main_knobs()

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.preferences_button = QPushButton()
        preferences_icon = QIcon.fromTheme("preferences-system")
        if preferences_icon.isNull():
            preferences_icon = QIcon.fromTheme("configure")
        if not preferences_icon.isNull():
            self.preferences_button.setIcon(preferences_icon)
            self.preferences_button.setIconSize(QSize(18, 18))
        else:
            self.preferences_button.setText("⚙")
        self.preferences_button.setToolTip(
            wrapped_tooltip(
                "Preferences\n"
                "Opens the full settings panel: MIDI Input/Output, "
                "Layouts, MIDI Filter, Randomizer, Randomization Behavior "
                "and Display."
            )
        )
        self.preferences_button.clicked.connect(self.open_preferences)
        self.preferences_button.setFixedWidth(
            self.fontMetrics().horizontalAdvance("M")
            + self.style().pixelMetric(QStyle.PixelMetric.PM_ButtonMargin) * 2
        )
        controls.addWidget(self.preferences_button)

        self.preset_label = QLabel("Preset:")
        controls.addWidget(self.preset_label)
        self.main_preset_combo = QComboBox()
        self.main_preset_combo.addItem("Custom — current settings", None)
        for preset_name, preset_values in RandomizerBehaviorPage.PRESETS:
            self.main_preset_combo.addItem(preset_name, preset_values)
        self.main_preset_combo.setToolTip(
            wrapped_tooltip(
                "Preset\n"
                "Selects a ready-made randomization profile.\n"
                "The full preset is applied immediately; the PLAY/STOP state "
                "without changing it.\n"
                "After a manual change, the selection switches to Custom."
            )
        )
        self.main_preset_combo.currentIndexChanged.connect(
            self.main_preset_changed
        )
        controls.addWidget(self.main_preset_combo, 1)

        self.main_preset_help_button = QPushButton("?")
        self.main_preset_help_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.main_preset_help_button.setFixedWidth(28)
        self.main_preset_help_button.setToolTip(
            wrapped_tooltip(
                "Preset help\n"
                "Shows the selected preset’s purpose and full "
                "parameters."
            )
        )
        self.main_preset_help_button.clicked.connect(
            self.show_main_preset_help
        )
        controls.addWidget(self.main_preset_help_button)



        self.randomizer_start_button = QPushButton()
        self.randomizer_start_button.setCheckable(True)
        self.randomizer_start_button.setMinimumWidth(52)
        self.randomizer_start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self._sync_output_status_in_preferences(False)
        self.debug_log("RND PAN: DEACTIVATED")
        self.randomizer_start_button.setIconSize(QSize(18, 18))
        self.randomizer_start_button.setToolTip(
            wrapped_tooltip(
                "PLAY / STOP\n"
                "Starts or stops MIDI randomization.\n"
                "Incoming Note On events are processed while PLAY is active.\n"
                "TEST does not send MIDI messages."
            )
        )
        self.randomizer_start_button.clicked.connect(
            self.toggle_randomizer
        )
        self.debug_panel_toggle = QPushButton("Log  ▾")
        self.debug_panel_toggle.setMaximumWidth(64)
        self.debug_panel_toggle.setCheckable(True)
        self.debug_panel_toggle.toggled.connect(self.toggle_debug_panel)
        controls.addWidget(self.debug_panel_toggle)
        controls.addWidget(self.randomizer_start_button)
        self.apply_button_colors()
        self.apply_combo_colors()
        central_layout.addLayout(controls)

        self.debug_panel = QPlainTextEdit(central)
        self.debug_panel.setReadOnly(True)
        self.debug_panel.document().setMaximumBlockCount(200)
        self.debug_panel.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.debug_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.debug_panel.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.debug_panel.setVisible(False)
        self.debug_panel.setFixedHeight(self.fontMetrics().lineSpacing() * self.debug_panel_rows + 12)
        self.debug_panel.setPlaceholderText("Debug messages will appear here.")
        if self._debug_messages:
            self.debug_panel.setPlainText("\n".join(self._debug_messages[-200:]))
        central_layout.addWidget(self.debug_panel)
        # Apply the active theme to the log immediately, not only after a theme change.
        self.apply_window_text_colors()
        self.debug_queue_timer = QTimer(self)
        self.debug_queue_timer.setInterval(100)
        self.debug_queue_timer.timeout.connect(self._drain_backend_debug_queue)
        self.debug_queue_timer.start()
        if self.open_terminal_for_debug:
            QTimer.singleShot(250, self.open_debug_terminal)

        self.randomizer_timer = QTimer(self)
        self.randomizer_timer.setInterval(randomizer.interval_ms)
        self.randomizer_timer.timeout.connect(self.generate_randomizer_value)

        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(50)
        self.activity_timer.timeout.connect(
            self.poll_midi_activity
        )
        self.activity_timer.start()

        self.generated_value_timer = QTimer(self)
        self.generated_value_timer.setInterval(30)
        self.generated_value_timer.timeout.connect(
            self.poll_generated_randomizer_values
        )
        self.generated_value_timer.start()

        self.activity_clear_timer = QTimer(self)
        self.activity_clear_timer.setSingleShot(True)
        self.activity_clear_timer.setInterval(120)
        self.activity_clear_timer.timeout.connect(
            self.clear_midi_activity
        )

        for widget in self.channel_widgets:
            widget.set_midi_activity(False)
            widget.set_value(0)

        self.apply_resize_mode()

        if self.start_in_play:
            self.randomizer_start_button.setChecked(True)
            self.toggle_randomizer(True)

        apply_wrapped_tooltips(self)

        saved_width = self.window_width
        self.set_window_width(saved_width)

        QTimer.singleShot(
            0,
            self._initialize_knob_scaling,
        )
        QTimer.singleShot(
            0,
            self._update_compact_control_labels,
        )
        QTimer.singleShot(
            0,
            self._update_main_knob_sizes,
        )

    def _initialize_knob_scaling(self):
        # The main graph width is the authoritative visual scale for the
        # four knobs plus the distribution selector share the available width.
        self._knob_reference_window_width = 290
        self._update_main_knob_sizes()

    def _update_main_knob_sizes(self):
        central = self.centralWidget()
        if central is None:
            return

        available_width = max(1, central.width() - 12)

        # One selector contains the square graph plus its arrow column;
        # four ordinary knobs use one diameter each.
        fitted_size = int((available_width - 84) / 5.4)

        size = max(44, min(140, fitted_size))

        selector = getattr(self, "main_distribution_selector", None)
        if selector is not None:
            selector.set_control_size(size)

        for knob in (
            getattr(self, "main_bias_knob", None),
            getattr(self, "main_change_knob", None),
            getattr(self, "main_interval_knob", None),
            getattr(self, "main_width_knob", None),
        ):
            if knob is not None:
                knob.set_knob_size(size)


    def randomizer_range_changed_from_preferences(self):
        """Apply a live Preferences range change to the main window."""
        randomizer.set_runtime_range(randomizer.minimum, randomizer.maximum)
        self._sync_main_knobs()
        self._sync_main_preset_status()
        self.persist_randomizer_settings()

    def _update_compact_control_labels(self):
        compact = self.width() < 445
        captions = (
            ("main_distribution_selector", "Dist." if compact else "Distribution"),
            ("main_bias_knob", "Bias"),
            ("main_change_knob", "Max Chg." if compact else "Max. Change"),
            ("main_interval_knob", "Int. Shift" if compact else "Interval Shift"),
            ("main_width_knob", "Width"),
        )
        for attribute, caption in captions:
            control = getattr(self, attribute, None)
            if control is None:
                continue
            if attribute == "main_distribution_selector":
                control._caption = caption
                control.caption_label.setText(caption)
                control.set_compact_labels(compact)
            else:
                control.set_caption(caption)
        if hasattr(self, "preset_label"):
            self.preset_label.setText("" if compact else "Preset:")

    def _sync_main_knobs(self):
        if not hasattr(self, "main_bias_knob"):
            return
        base_low, base_high = randomizer.range
        runtime_low, runtime_high = randomizer.runtime_range
        center = (base_low + base_high) / 2.0
        max_half_width = max(center, MIDI_MAX - center)
        self.main_width_knob.dial.setRange(0, int(round(max_half_width)))
        self.main_interval_knob.dial.setRange(-base_low, MIDI_MAX - base_high)
        self.main_range_indicator.set_values(runtime_low, runtime_high)
        self.main_distribution_selector.set_distribution(randomizer.distribution)
        self.main_distribution_selector.set_bias(randomizer.bias)
        for knob, value in (
            (self.main_bias_knob, randomizer.bias),
            (self.main_change_knob, randomizer.max_change),
            (self.main_interval_knob, runtime_low - base_low),
            (self.main_width_knob, int(round((base_high - base_low) / 2.0))),
        ):
            knob.set_value(value)

    def main_interval_changed(self, value):
        """Shift the complete runtime PAN interval without changing its width."""
        offset = int(value)
        low, high = randomizer.range
        low = max(MIDI_MIN, min(MIDI_MAX, low + offset))
        high = max(MIDI_MIN, min(MIDI_MAX, high + offset))
        if low > high:
            low, high = high, low
        randomizer.set_runtime_range(low, high)
        self.main_range_indicator.set_values(low, high)
        self._sync_main_knobs()
        self._sync_main_preset_status()
        self.persist_randomizer_settings()

    def main_width_changed(self, value):
        """Resize the base PAN interval symmetrically around its center."""
        base_low, base_high = randomizer.range
        runtime_low, runtime_high = randomizer.runtime_range
        offset = runtime_low - base_low
        center = (base_low + base_high) / 2.0
        half_width = max(0, int(value))
        low = max(MIDI_MIN, int(round(center - half_width)))
        high = min(MIDI_MAX, int(round(center + half_width)))
        if low > high:
            low, high = high, low
        randomizer.set_range(low, high)
        shifted_low = max(MIDI_MIN, min(MIDI_MAX, low + offset))
        shifted_high = max(MIDI_MIN, min(MIDI_MAX, high + offset))
        if shifted_low > shifted_high:
            shifted_low, shifted_high = shifted_high, shifted_low
        randomizer.set_runtime_range(shifted_low, shifted_high)
        self.main_range_indicator.set_values(shifted_low, shifted_high)
        self._sync_main_knobs()
        self._sync_main_preset_status()
        self.persist_randomizer_settings()

    def main_distribution_changed(self, index):
        distributions = MidiRandomizer.DISTRIBUTIONS
        index = max(0, min(len(distributions) - 1, int(index)))
        distribution = distributions[index][0]
        randomizer.set_distribution(distribution)

        preferences_dialog = getattr(self, "_preferences_dialog", None)
        behavior = (
            getattr(preferences_dialog, "randomizer_behavior_page", None)
            if preferences_dialog is not None
            else None
        )
        if behavior is not None:
            behavior.distribution_combo.blockSignals(True)
            try:
                combo_index = behavior.distribution_combo.findData(
                    distribution
                )
                if combo_index >= 0:
                    behavior.distribution_combo.setCurrentIndex(combo_index)
            finally:
                behavior.distribution_combo.blockSignals(False)

        self._sync_main_preset_status()
        self.persist_randomizer_settings()

    def main_knob_double_clicked(self, value):
        sender = self.sender()
        caption = (
            sender._caption
            if isinstance(sender, MainRotaryKnob)
            else "Knob"
        )

        if caption in ("Maximum Change", "Width"):
            display_value = f"±{int(value)}"
        else:
            display_value = str(int(value))

        self.debug_log(
            f"Double-click → {caption} = {display_value}"
        )

    def main_bias_changed(self, value):
        randomizer.set_bias(value)
        self.main_distribution_selector.set_bias(randomizer.bias)
        preferences_dialog = getattr(self, "_preferences_dialog", None)
        behavior = (
            getattr(preferences_dialog, "randomizer_behavior_page", None)
            if preferences_dialog is not None
            else None
        )
        if behavior is not None:
            behavior.bias_slider.setValue(randomizer.bias)
        self._sync_main_preset_status()
        self.persist_randomizer_settings()

    def main_change_changed(self, value):
        randomizer.set_max_change(value)
        preferences_dialog = getattr(self, "_preferences_dialog", None)
        behavior = (
            getattr(preferences_dialog, "randomizer_behavior_page", None)
            if preferences_dialog is not None
            else None
        )
        if behavior is not None:
            behavior.change_slider.setValue(randomizer.max_change)
        self._sync_main_preset_status()
        self.persist_randomizer_settings()

    def main_range_indicator_changed(self, low, high):
        randomizer.set_range(low, high)
        randomizer.set_runtime_range(low, high)
        dialog = getattr(self, "_preferences_dialog", None)
        page = getattr(dialog, "randomizer_page", None) if dialog else None
        if page is not None:
            page.minimum_spin.blockSignals(True)
            page.maximum_spin.blockSignals(True)
            page.minimum_spin.setValue(low)
            page.maximum_spin.setValue(high)
            page.minimum_spin.blockSignals(False)
            page.maximum_spin.blockSignals(False)
            page.range_slider.set_values(low, high)
        center = (low + high) / 2.0
        self.main_interval_knob.dial.setRange(
            0, int(round(max(center, MIDI_MAX-center)))
        )
        self.main_interval_knob.set_value(int(round((high-low)/2.0)))
        self._sync_main_preset_status()
        self.save_preferences(self.window_size, self.window_resizable)

    def main_preset_changed(self, index):
        preset = self.main_preset_combo.itemData(index)
        if not preset:
            return

        # Preset changes are live: keep the current PLAY/STOP state.
        # This lets the user audition presets while MIDI is passing through.

        # Apply the same preset definition used by Preferences /
        # Randomizer Behavior.  Keep the Preferences controls synchronized
        # if that dialog is currently open.
        behavior = None
        preferences_dialog = getattr(self, "_preferences_dialog", None)
        if preferences_dialog is not None:
            behavior = getattr(
                preferences_dialog,
                "randomizer_behavior_page",
                None,
            )

        randomizer_page = (
            getattr(preferences_dialog, "randomizer_page", None)
            if preferences_dialog is not None
            else None
        )

        if randomizer_page is not None:
            randomizer_page._minimum_changed(preset["minimum"])
            randomizer_page._maximum_changed(preset["maximum"])
        else:
            randomizer.set_range(
                preset["minimum"],
                preset["maximum"],
            )

        randomizer.set_distribution(preset["distribution"])
        randomizer.set_bias(preset["bias"])
        randomizer.set_max_change(preset["max_change"])
        randomizer.set_prevent_duplicates(
            preset["prevent_duplicates"]
        )
        randomizer.set_avoid_recent(
            preset["avoid_recent"],
            preset["recent_history"],
        )
        randomizer.set_interval(preset["interval_ms"])
        randomizer.set_humanize(preset["humanize"])
        self.randomizer_timer.setInterval(randomizer.interval_ms)
        self._sync_main_knobs()

        if behavior is not None:
            behavior.distribution_combo.setCurrentIndex(
                behavior.distribution_combo.findData(
                    preset["distribution"]
                )
            )
            behavior.bias_slider.setValue(preset["bias"])
            behavior.change_slider.setValue(preset["max_change"])
            behavior.duplicate_checkbox.setChecked(
                preset["prevent_duplicates"]
            )
            behavior.recent_checkbox.setChecked(
                preset["avoid_recent"]
            )
            behavior.history_spin.setValue(
                preset["recent_history"]
            )
            behavior.interval_spin.setValue(
                preset["interval_ms"]
            )
            behavior.interval_slider.setValue(
                preset["interval_ms"]
            )
            behavior.humanize_spin.setValue(
                preset["humanize"]
            )
            behavior._update_preset_status()

        # Final authoritative refresh: every visible control is now derived
        # from the same live randomizer state.
        self._sync_main_knobs()
        if behavior is not None:
            behavior._update_preset_status()
        self.persist_randomizer_settings()

    def show_main_preset_help(self):
        """Show the current preset purpose and complete parameters."""
        index = self.main_preset_combo.currentIndex()
        selected_name = self.main_preset_combo.currentText()
        values = self.main_preset_combo.itemData(index)

        if values:
            name = selected_name
            matched = True
        else:
            name = "Custom — current settings"
            matched = False
            values = {
                "minimum": randomizer.minimum,
                "maximum": randomizer.maximum,
                "distribution": randomizer.distribution,
                "bias": randomizer.bias,
                "max_change": randomizer.max_change,
                "prevent_duplicates": randomizer.prevent_duplicates,
                "avoid_recent": randomizer.avoid_recent,
                "recent_history": randomizer.recent_history,
                "interval_ms": randomizer.interval_ms,
                "humanize": randomizer.humanize,
            }

        preferences_dialog = getattr(
            self,
            "_preferences_dialog",
            None,
        )
        behavior = (
            getattr(
                preferences_dialog,
                "randomizer_behavior_page",
                None,
            )
            if preferences_dialog is not None
            else None
        )
        descriptions = (
            getattr(behavior, "_preset_descriptions", {})
            if behavior is not None
            else {}
        )

        if matched:
            purpose = descriptions.get(
                name,
                "The preset configures the complete randomization behaviour at once.",
            )
        else:
            purpose = (
                "Custom represents the current manually configured "
                "randomization values."
            )

        distribution_label = dict(
            MidiRandomizer.DISTRIBUTIONS
        ).get(
            values["distribution"],
            values["distribution"],
        )
        humanize_text = (
            "Original (±0)"
            if values["humanize"] == 0
            else f"±{values['humanize']}"
        )

        popup = QFrame(
            self,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint,
        )
        popup.setFrameShape(QFrame.Shape.StyledPanel)
        popup.setStyleSheet(
            "QFrame {"
            "background: white;"
            "border: 1px solid #777777;"
            "border-radius: 4px;"
            "}"
            "QLabel { color: #000000; }"
        )

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        title = QLabel(name)
        title.setStyleSheet(
            "font-weight: bold; font-size: 13px;"
        )
        layout.addWidget(title)

        purpose_label = QLabel(purpose)
        purpose_label.setWordWrap(True)
        purpose_label.setMaximumWidth(390)
        layout.addWidget(purpose_label)

        detail = QLabel(
            f"Range: {values['minimum']}–{values['maximum']}\n"
            f"Distribution: {distribution_label}\n"
            f"Bias: {values['bias']:+d}\n"
            f"Max. Change: ±{values['max_change']}\n"
            f"Prevent duplicates: "
            f"{'ON' if values['prevent_duplicates'] else 'OFF'}\n"
            f"Avoid recent: "
            f"{'ON' if values['avoid_recent'] else 'OFF'}\n"
            f"History: {values['recent_history']}\n"
            f"Humanize: {humanize_text}\n"
            f"Interval: {values['interval_ms']} ms"
        )
        detail.setWordWrap(True)
        detail.setStyleSheet("font-size: 11px; color: #222222;")
        layout.addWidget(detail)

        popup.adjustSize()
        point = self.main_preset_help_button.mapToGlobal(
            self.main_preset_help_button.rect().bottomLeft()
        )
        popup.move(point)
        popup.show()

    def _sync_main_preset_status(self):
        if not hasattr(self, "main_preset_combo"):
            return

        current = {
            "minimum": randomizer.minimum,
            "maximum": randomizer.maximum,
            "distribution": randomizer.distribution,
            "bias": randomizer.bias,
            "max_change": randomizer.max_change,
            "prevent_duplicates": randomizer.prevent_duplicates,
            "avoid_recent": randomizer.avoid_recent,
            "recent_history": randomizer.recent_history,
            "interval_ms": randomizer.interval_ms,
            "humanize": randomizer.humanize,
        }

        matched = None
        for name, values in RandomizerBehaviorPage.PRESETS:
            if current == values:
                matched = name
                break

        self.main_preset_combo.blockSignals(True)
        try:
            if matched is None:
                self.main_preset_combo.setCurrentIndex(0)
                self.main_preset_combo.setItemText(
                    0, "Custom — current settings"
                )
            else:
                index = self.main_preset_combo.findText(matched)
                if index >= 0:
                    self.main_preset_combo.setCurrentIndex(index)
        finally:
            self.main_preset_combo.blockSignals(False)


    def poll_generated_randomizer_values(self):
        """Update the existing graph/UI with values generated by Note On events."""
        backend = self.backend
        if not hasattr(backend, "take_generated_values"):
            return

        values = backend.take_generated_values()
        if not values:
            return

        for value in values:
            self.midi_pan = value
            self.randomizer_graph.add_value(value)

            preferences_dialog = getattr(
                self, "_preferences_dialog", None
            )
            behavior = (
                getattr(
                    preferences_dialog,
                    "randomizer_behavior_page",
                    None,
                )
                if preferences_dialog is not None
                else None
            )
            if behavior is not None:
                behavior.result_label.setText(str(value))
                behavior._update_change_display()

        self._sync_main_preset_status()

    def toggle_randomizer(self, checked):
        backend = self.backend
        if hasattr(backend, "set_randomization_enabled"):
            backend.set_randomization_enabled(bool(checked))

        if checked:
            self.randomizer_start_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
            )
            self._sync_output_status_in_preferences(True)
            self.debug_log("RND PAN: ACTIVATED")
        else:
            self.stop_randomizer()

    def stop_randomizer(self):
        if hasattr(self.backend, "set_randomization_enabled"):
            self.backend.set_randomization_enabled(False)

        self.randomizer_timer.stop()
        self.randomizer_start_button.setChecked(False)
        self.randomizer_start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self._sync_output_status_in_preferences(False)

    def _sync_output_status_in_preferences(self, running):
        dialog = getattr(self, "_preferences_dialog", None)
        if dialog is None:
            return
        page = getattr(dialog, "randomizer_behavior_page", None)
        if page is not None:
            page.set_output_running(running)

    def generate_randomizer_value(self):
        value = randomizer.generate()
        self.midi_pan = value
        self.randomizer_graph.add_value(value)

        self.debug_log(
            "Randomize: "
            f"distribution={randomizer.distribution} "
            f"range={randomizer.minimum}-{randomizer.maximum} "
            f"bias={randomizer.bias:+d} "
            f"max_change={randomizer.max_change} "
            f"prevent_duplicates={randomizer.prevent_duplicates} "
            f"avoid_recent={randomizer.avoid_recent} "
            f"history={randomizer.recent_history} "
            f"speed={randomizer.interval_ms}ms "
            f"humanize=±{randomizer.humanize} "
            f"value={value}"
        )

        preferences_dialog = getattr(self, "_preferences_dialog", None)
        behavior = (
            getattr(preferences_dialog, "randomizer_behavior_page", None)
            if preferences_dialog is not None
            else None
        )
        if behavior is not None:
            behavior.result_label.setText(str(value))
            behavior._update_change_display()

        self._sync_main_preset_status()

    def load_visibility_preferences(self):
        defaults = {
            "show_graph": True,
            "show_controls": True,
            "show_interval": True,
        }
        if not PREFERENCES_FILE.exists():
            return defaults
        try:
            data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return defaults
        return {key: bool(data.get(key, default)) for key, default in defaults.items()}

    def load_start_in_play(self):
        if not PREFERENCES_FILE.exists():
            return False
        try:
            data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
            return bool(data.get("start_in_play", False))
        except (OSError, ValueError, TypeError):
            return False

    def set_start_in_play(self, enabled):
        self.start_in_play = bool(enabled)
        self.save_preferences(self.window_size, self.window_resizable)

    def apply_main_element_visibility(self):
        graph = getattr(self, "graph_container", None)
        controls = getattr(self, "main_controls_container", None)
        interval = getattr(self, "main_range_indicator", None)
        if graph is not None:
            graph.setVisible(self.show_graph)
        if controls is not None:
            controls.setVisible(self.show_controls)
        if interval is not None:
            interval.setVisible(self.show_interval)

    def set_main_element_visibility(self, element, visible):
        attribute = {
            "graph": "show_graph",
            "controls": "show_controls",
            "interval": "show_interval",
        }.get(element)
        if attribute is None:
            return
        setattr(self, attribute, bool(visible))
        self.apply_main_element_visibility()
        self.save_preferences(self.window_size, self.window_resizable)

    def load_layout(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_LAYOUT

        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            layout = data.get("layout", DEFAULT_LAYOUT)
            return layout if layout in LAYOUTS else DEFAULT_LAYOUT
        except (OSError, ValueError, TypeError):
            return DEFAULT_LAYOUT

    def rebuild_channel_layout(self):
        """Keep the main window occupied by the randomizer graph."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.randomizer_graph:
                widget.setParent(self.centralWidget())

        self.grid_layout.setRowStretch(0, 1)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.addWidget(self.randomizer_graph, 0, 0)

    def layout_aspect_ratio(self, layout_mode=None):
        if layout_mode is None:
            layout_mode = self.layout_mode
        return LAYOUT_ASPECT_RATIOS.get(
            layout_mode,
            LAYOUT_ASPECT_RATIOS[DEFAULT_LAYOUT],
        )

    def fit_geometry_to_screen(self, width, height):
        screen = self.screen()
        if screen is None:
            return width, height

        available = screen.availableGeometry()
        max_width = max(1, available.width())
        max_height = max(1, available.height())

        # Preserve the requested aspect ratio while ensuring the complete
        # window, including its title bar, can fit on the usable screen.
        scale = min(
            1.0,
            max_width / max(1, width),
            max_height / max(1, height),
        )

        width = max(1, int(round(width * scale)))
        height = max(1, int(round(height * scale)))
        return width, height

    def resize_for_layout(self, layout_mode=None):
        ratio = self.layout_aspect_ratio(layout_mode)

        # Preserve the current window area while changing only its aspect ratio.
        current_width = max(1, self.width())
        current_height = max(1, self.height())
        area = current_width * current_height

        width = max(1, int(round((area * ratio) ** 0.5)))
        height = max(1, int(round((area / ratio) ** 0.5)))

        # Keep the short side within the configured useful range. The long
        # side is then derived from the selected aspect ratio.
        short_side = min(width, height)
        if short_side < MIN_SIZE:
            scale = MIN_SIZE / short_side
            width = int(round(width * scale))
            height = int(round(height * scale))

        long_side = max(width, height)
        if long_side > MAX_SIZE:
            scale = MAX_SIZE / long_side
            width = int(round(width * scale))
            height = int(round(height * scale))

        width, height = self.fit_geometry_to_screen(width, height)

        self._resizing_layout = True
        self.setMinimumSize(QSize(1, 1))
        self.setMaximumSize(QSize(MAX_SIZE, MAX_SIZE))
        self.resize(width, height)
        self._resizing_layout = False

        # Keep the title bar/top edge visible on the current screen.
        # This is especially important for tall 2x8/1x16 vertical layouts.
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            geometry = self.geometry()

            if geometry.top() < available.top():
                geometry.moveTop(available.top())

            if geometry.bottom() > available.bottom():
                geometry.moveTop(
                    max(
                        available.top(),
                        available.bottom() - geometry.height() + 1,
                    )
                )

            if geometry.left() < available.left():
                geometry.moveLeft(available.left())

            if geometry.right() > available.right():
                geometry.moveLeft(
                    max(
                        available.left(),
                        available.right() - geometry.width() + 1,
                    )
                )

            self.setGeometry(geometry)

        self.window_size = max(width, height)

    def set_window_resizable(self, enabled):
        self.window_resizable = bool(enabled)

        if self.window_resizable:
            min_width, min_height = self.layout_minimum_dimensions()
            self.setMinimumSize(
                QSize(min_width, min_height)
            )
            self.setMaximumSize(
                QSize(MAX_SIZE, MAX_SIZE)
            )
        else:
            self.setMinimumSize(self.size())
            self.setMaximumSize(self.size())

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_layout_mode(self, layout_mode):
        if layout_mode not in LAYOUTS:
            return

        # The horizontal Window Width is preserved across layout changes.
        # Capture it before rebuilding the grid, then derive the new height
        # from the newly selected layout.
        current_width = max(
            MIN_SIZE,
            min(MAX_SIZE, self.width()),
        )

        self.layout_mode = layout_mode
        self.rebuild_channel_layout()

        self.setMinimumSize(QSize(1, 1))
        self.setMaximumSize(QSize(MAX_SIZE, MAX_SIZE))
        self.set_window_width(current_width)

        if self.window_resizable:
            min_width, min_height = self.layout_minimum_dimensions()
            self.setMinimumSize(
                QSize(min_width, min_height)
            )
            self.setMaximumSize(
                QSize(MAX_SIZE, MAX_SIZE)
            )
        else:
            self.setMinimumSize(self.size())
            self.setMaximumSize(self.size())

        # Keep the Preferences value synchronized immediately while the
        # dialog is open.
        preferences_dialog = getattr(
            self,
            "_preferences_dialog",
            None,
        )
        if preferences_dialog is not None:
            preferences_dialog.sync_layout_settings(
                self.layout_mode,
                self.window_resizable,
            )

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def show_window_context_menu(self, global_pos):
        """Show the compact menu available in both framed and frameless modes."""
        menu = QMenu(self)

        frame_action = QAction(
            "Window frame",
            self,
        )
        frame_action.setCheckable(True)
        frame_action.setChecked(not bool(self._frameless))
        frame_action.setToolTip(
            "Show or hide the window frame."
        )
        frame_action.triggered.connect(
            lambda checked: self.set_frameless_window_preference(
                not bool(checked)
            )
        )
        menu.addAction(frame_action)

        rnd_value_action = QAction(
            "RND Value",
            self,
        )
        rnd_value_action.setCheckable(True)
        rnd_value_action.setChecked(
            bool(self.show_current_rnd_value)
        )
        rnd_value_action.triggered.connect(
            self.set_show_current_rnd_value
        )
        menu.addAction(rnd_value_action)

        reset_graph_action = QAction(
            "Reset graph on left click",
            self,
        )
        reset_graph_action.setCheckable(True)
        reset_graph_action.setChecked(
            bool(self.reset_graph_on_left_click)
        )
        reset_graph_action.triggered.connect(
            self.set_reset_graph_on_left_click
        )
        menu.addAction(reset_graph_action)

        debug_action = QAction(
            "Debug to terminal",
            self,
        )
        debug_action.setCheckable(True)
        debug_action.setChecked(
            bool(self.debug_to_terminal)
        )
        debug_action.triggered.connect(
            self.set_debug_to_terminal
        )
        menu.addAction(debug_action)

        preferences = QAction(
            "Preferences",
            self,
        )
        preferences.triggered.connect(
            self.open_preferences
        )
        menu.addAction(preferences)

        quit_action = QAction(
            "Quit",
            self,
        )
        quit_action.triggered.connect(
            self.request_quit
        )
        menu.addAction(quit_action)

        menu.exec(global_pos)

    def contextMenuEvent(self, event):
        self.show_window_context_menu(event.globalPos())
        event.accept()

    def show_channel_context_menu(self, channel, global_pos):
        self.show_window_context_menu(global_pos)

    def _frameless_drag_allowed(self, watched):
        """Return True only for non-interactive window/background areas."""
        widget = watched
        while widget is not None:
            if widget is self:
                return True

            # These widgets own the mouse interaction; dragging the window
            # from them would interfere with their normal controls.
            if isinstance(
                widget,
                (
                    QPushButton,
                    QCheckBox,
                    QComboBox,
                    QSlider,
                    QDial,
                    QSpinBox,
                    QLineEdit,
                    QPlainTextEdit,
                    QListWidget,
                    RandomizerGraphWidget,
                    MainRangeIndicator,
                    MainRotaryKnob,
                    DistributionSelector,
                ),
            ):
                return False

            widget = widget.parentWidget()

        return False

    def _frameless_edges_at(self, global_pos):
        """Return resize edges under the pointer, or None away from borders."""
        if not self._frameless or not self.window_resizable or not self.isVisible():
            return None
        frame = self.frameGeometry()
        x, y = global_pos.x(), global_pos.y()
        margin = 9
        edges = set()
        if x <= frame.left() + margin:
            edges.add("left")
        elif x >= frame.right() - margin:
            edges.add("right")
        if y <= frame.top() + margin:
            edges.add("top")
        elif y >= frame.bottom() - margin:
            edges.add("bottom")
        return edges or None

    def _set_frameless_resize_cursor(self, edges):
        if not edges:
            self.unsetCursor()
            return
        horizontal = "left" in edges or "right" in edges
        vertical = "top" in edges or "bottom" in edges
        if horizontal and vertical:
            if ("left" in edges and "top" in edges) or ("right" in edges and "bottom" in edges):
                shape = Qt.CursorShape.SizeFDiagCursor
            else:
                shape = Qt.CursorShape.SizeBDiagCursor
        elif horizontal:
            shape = Qt.CursorShape.SizeHorCursor
        else:
            shape = Qt.CursorShape.SizeVerCursor
        self.setCursor(shape)

    def _resize_frameless_window(self, global_pos):
        if not self._frameless_resize_edges or self._frameless_resize_geometry is None:
            return
        start = self._frameless_resize_start
        dx = global_pos.x() - start.x()
        dy = global_pos.y() - start.y()
        g = self._frameless_resize_geometry
        left, top, right, bottom = g.left(), g.top(), g.right(), g.bottom()
        edges = self._frameless_resize_edges
        if "left" in edges:
            left = min(right - self.minimumWidth(), left + dx)
        if "right" in edges:
            right = max(left + self.minimumWidth() - 1, right + dx)
        if "top" in edges:
            top = min(bottom - self.minimumHeight(), top + dy)
        if "bottom" in edges:
            bottom = max(top + self.minimumHeight() - 1, bottom + dy)
        new_width = min(self.maximumWidth(), right - left + 1)
        new_height = min(self.maximumHeight(), bottom - top + 1)
        if "left" in edges:
            left = right - new_width + 1
        if "top" in edges:
            top = bottom - new_height + 1
        self.setGeometry(left, top, new_width, new_height)

    def eventFilter(self, watched, event):
        # The filter is installed on QApplication, so `watched` can itself
        # be the QApplication object. Only QWidget instances can safely be
        # tested with .window(). Preferences and other dialogs stay untouched.
        if watched is self:
            watched_is_main_window = True
        elif isinstance(watched, QWidget):
            watched_is_main_window = (
                watched.window() is self
            )
        else:
            watched_is_main_window = False

        if not watched_is_main_window:
            return super().eventFilter(watched, event)

        # Frameless windows have no native border, so resize by dragging an
        # 9-pixel hit area at the edges/corners. Handle this before move logic.
        if self._frameless and self.window_resizable:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                edges = self._frameless_edges_at(global_pos)
                if edges:
                    self._frameless_resize_edges = edges
                    self._frameless_resize_start = global_pos
                    self._frameless_resize_geometry = self.geometry()
                    self._frameless_drag_start = None
                    self._frameless_drag_offset = None
                    self._frameless_drag_active = False
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                global_pos = event.globalPosition().toPoint()
                if self._frameless_resize_edges:
                    self._resize_frameless_window(global_pos)
                    return True
                self._set_frameless_resize_cursor(self._frameless_edges_at(global_pos))
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self._frameless_resize_edges:
                    self._frameless_resize_edges = None
                    self._frameless_resize_geometry = None
                    self._frameless_resize_start = None
                    self.save_preferences(self.window_size, self.window_resizable)
                    self._set_frameless_resize_cursor(self._frameless_edges_at(event.globalPosition().toPoint()))
                    return True

        # Alt+Space uses the same compact context menu in both framed and
        # frameless modes. This deliberately replaces the native window
        # system menu for this application window.
        if event.type() == QEvent.Type.KeyPress:
            if (
                event.key() == Qt.Key.Key_Space
                and event.modifiers() & Qt.KeyboardModifier.AltModifier
            ):
                self.show_window_context_menu(
                    self.mapToGlobal(self.rect().center())
                )
                event.accept()
                return True

        # A left drag on non-interactive background moves the whole window.
        # This is intentionally independent of the frame state: framed
        # windows can be moved from their content background too, while all
        # knobs/graph/range/button controls retain their own mouse behavior.
        if self._frameless_drag_allowed(watched):
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    global_pos = event.globalPosition().toPoint()
                    self._frameless_drag_start = global_pos
                    self._frameless_drag_offset = (
                        global_pos - self.frameGeometry().topLeft()
                    )
                    self._frameless_drag_active = False
                    return False

            elif event.type() == QEvent.Type.MouseMove:
                if self._frameless_drag_start is not None:
                    current = event.globalPosition().toPoint()
                    dx = current.x() - self._frameless_drag_start.x()
                    dy = current.y() - self._frameless_drag_start.y()

                    if (
                        not self._frameless_drag_active
                        and (abs(dx) >= 5 or abs(dy) >= 5)
                    ):
                        self._frameless_drag_active = True

                    if self._frameless_drag_active:
                        self.move(
                            current - self._frameless_drag_offset
                        )
                        return True

            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    was_dragging = self._frameless_drag_active
                    self._frameless_drag_start = None
                    self._frameless_drag_offset = None
                    self._frameless_drag_active = False
                    if was_dragging:
                        return True

        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._frameless_drag_start = None
        self._frameless_drag_offset = None
        self._frameless_drag_active = False
        self._frameless_resize_edges = None
        self._frameless_resize_geometry = None
        self._frameless_resize_start = None
        super().closeEvent(event)

    def toggle_frameless_window(self, enabled):
        enabled = bool(enabled)

        if enabled == self._frameless:
            return

        geometry = self.geometry()
        was_visible = self.isVisible()

        replacement = MidiRandomizeWindow(
            backend=self.backend,
            frameless=enabled,
        )
        replacement.window_size = self.window_size
        replacement.window_resizable = self.window_resizable
        replacement.show_channel_labels = self.show_channel_labels
        replacement.show_active_status = self.show_active_status
        replacement.active_status_text = self.active_status_text
        replacement.window_width = self.window_width
        replacement.background_color = self.background_color
        replacement.channel_label_color = self.channel_label_color
        replacement.active_text_color = getattr(
            self,
            "active_text_color",
            self.window_text_color,
        )
        replacement.active_background_color = getattr(
            self,
            "active_background_color",
            self.background_color,
        )
        replacement.debug_to_terminal = self.debug_to_terminal
        replacement.apply_background_color()
        replacement.update_channel_label_colors()
        for widget in replacement.channel_widgets:
            widget.channel_label.setVisible(
                replacement.show_channel_labels
            )
        replacement.apply_resize_mode()

        # Preserve current visual activity state during the replacement.
        for old_widget, new_widget in zip(
            self.channel_widgets,
            replacement.channel_widgets,
        ):
            new_widget.set_midi_activity(
                old_widget.midi_active
            )

        replacement.setGeometry(geometry)

        app = QApplication.instance()
        if app is not None:
            app._midi_randomize_window = replacement

        self._replacing_window = True

        if was_visible:
            replacement.show()
            replacement.raise_()
            replacement.activateWindow()

        self.close()

    def open_midi_monitor(self):
        if (
            hasattr(self, "_midi_monitor")
            and self._midi_monitor is not None
        ):
            self._midi_monitor.raise_()
            self._midi_monitor.activateWindow()
            return

        self._midi_monitor = MidiMonitorDialog(self)
        self._midi_monitor.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )
        self._midi_monitor.destroyed.connect(
            lambda: setattr(
                self,
                "_midi_monitor",
                None,
            )
        )
        self._midi_monitor.show()

    def _queue_backend_debug_message(self, message):
        try:
            self._backend_debug_queue.put(str(message))
        except Exception:
            pass

    def _drain_backend_debug_queue(self):
        while True:
            try:
                message = self._backend_debug_queue.get_nowait()
            except Exception:
                break
            self.debug_log(message)

    def debug_log(self, message):
        message = " | ".join(str(message).splitlines()).strip()
        timestamp = datetime.now(ZoneInfo("Europe/Budapest")).strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self._debug_messages.append(line)
        self._debug_messages = self._debug_messages[-200:]
        panel = getattr(self, "debug_panel", None)
        if panel is not None:
            panel.appendPlainText(line)
        if self.debug_to_terminal:
            print(line, flush=True)
        if getattr(self, "open_terminal_for_debug", False):
            try:
                with self._debug_log_file.open("a", encoding="utf-8") as stream:
                    stream.write(line + "\n")
            except OSError:
                pass

    def load_open_terminal_for_debug(self):
        try:
            data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
            return bool(data.get("open_terminal_for_debug", False))
        except (OSError, ValueError, TypeError):
            return False

    def load_debug_panel_rows(self):
        try:
            data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
            return max(2, min(10, int(data.get("debug_panel_rows", 5))))
        except (OSError, ValueError, TypeError):
            return 5

    def set_open_terminal_for_debug(self, enabled):
        self.open_terminal_for_debug = bool(enabled)
        if enabled:
            self.open_debug_terminal()
        else:
            self._debug_terminal_process = None
        self.save_preferences(self.window_size, self.window_resizable)

    def set_debug_panel_rows(self, rows):
        self.debug_panel_rows = max(2, min(10, int(rows)))
        panel = getattr(self, "debug_panel", None)
        if panel is not None:
            panel.setFixedHeight(self.fontMetrics().lineSpacing() * self.debug_panel_rows + 12)
        self.save_preferences(self.window_size, self.window_resizable)

    def toggle_debug_panel(self, expanded):
        panel = getattr(self, "debug_panel", None)
        if panel is None:
            return
        panel.setVisible(bool(expanded))
        self.debug_panel_toggle.setText("Log  ▴" if expanded else "Log  ▾")

    def open_debug_terminal(self):
        process = getattr(self, "_debug_terminal_process", None)
        if process is not None and process.poll() is None:
            return
        terminal = shutil.which("x-terminal-emulator") or shutil.which("xterm")
        if not terminal:
            self._append_debug_message("WARNING: no x-terminal-emulator or xterm executable was found.")
            return
        try:
            self._debug_log_file.touch(exist_ok=True)
            command = "printf '%s\n' 'RND PAN debug output'; " + f"tail -n {self.debug_panel_rows} -F {shlex.quote(str(self._debug_log_file))}"
            self._debug_terminal_process = subprocess.Popen(
                [terminal, "-e", "sh", "-lc", command], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
        except (OSError, TypeError) as exc:
            self._append_debug_message(f"ERROR: could not open debug terminal: {exc}")

    def _append_debug_message(self, line):
        self._debug_messages.append(str(line))
        self._debug_messages = self._debug_messages[-200:]
        if getattr(self, "debug_panel", None) is not None:
            self.debug_panel.appendPlainText(str(line))

    def add_randomizer_value(self, value):
        """Append one generated randomizer value to the live main-window graph."""
        self.randomizer_graph.add_value(value)

    def clear_randomizer_graph(self):
        """Clear the generated-value history shown in the main window."""
        self.randomizer_graph.clear_values()

    def apply_color_collection(self, name):
        """Apply a coordinated Velocity-style color collection to RND PAN."""
        if name == "Custom":
            self.color_collection = name
            return
        palette = COLOR_COLLECTIONS.get(name)
        if not palette:
            return
        self.color_collection = name
        mapping = {
            "background_color": "background_color",
            "button_background_color": "button_background_color",
            "button_text_color": "button_text_color",
            "combo_background_color": "combo_background_color",
            "combo_text_color": "combo_text_color",
            "graph_background_color": "graph_background_color",
            "graph_text_color": "graph_text_color",
            "graph_grid_color": "graph_grid_color",
            "graph_axis_color": "graph_axis_color",
            "graph_point_color": "graph_point_color",
            "window_text_background_color": "window_text_background_color",
            "window_text_color": "window_text_color",
            "pot_value_text_color": "pot_value_text_color",
            "pot_caption_text_color": "pot_caption_text_color",
            "range_text_color": "range_text_color",
            "arrow_background_color": "arrow_background_color",
            "arrow_text_color": "arrow_text_color",
            "distribution_graph_background_color": "distribution_graph_background_color",
            "distribution_graph_text_color": "distribution_graph_text_color",
            "rnd_value_color": "rnd_value_color",
        }
        for key, attr in mapping.items():
            if key in palette:
                setattr(self, attr, palette[key])
        self.apply_background_color()
        self.apply_button_colors()
        self.apply_combo_colors()
        self.apply_window_text_colors()
        self.apply_arrow_colors()
        self.apply_distribution_graph_colors()
        self.randomizer_graph.set_colors(
            self.graph_background_color, self.graph_grid_color,
            self.graph_axis_color, self.graph_text_color,
            self.graph_point_color,
        )
        self.randomizer_graph.set_rnd_value_color(self.rnd_value_color)
        if hasattr(self, "main_bias_knob"):
            for knob in (self.main_bias_knob, self.main_change_knob, self.main_interval_knob, self.main_width_knob):
                knob.set_display_colors(self.pot_value_text_color, self.pot_caption_text_color, self.window_text_background_color)
        self.persist_randomizer_settings()

    def set_graph_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.randomizer_graph.set_colors(
            self.graph_background_color,
            self.graph_grid_color,
            self.graph_axis_color,
            self.graph_text_color,
            self.graph_point_color,
        )
        # Main control labels use Window Text colors, independently
        # from the graph text color.
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def apply_window_text_colors(self):
        background = QColor(self.window_text_background_color)
        text_color = QColor(self.window_text_color)
        if not background.isValid():
            background = QColor(DEFAULT_WINDOW_TEXT_BACKGROUND_COLOR)
        if not text_color.isValid():
            text_color = QColor(DEFAULT_WINDOW_TEXT_COLOR)

        # Keep the collapsible debug log readable under every color collection.
        debug_panel = getattr(self, "debug_panel", None)
        if debug_panel is not None:
            debug_panel.setStyleSheet(
                "QPlainTextEdit {"
                f" background-color: {background.name()};"
                f" color: {text_color.name()};"
                f" border: 1px solid {self.graph_grid_color};"
                f" selection-background-color: {self.button_background_color};"
                f" selection-color: {self.button_text_color};"
                "}"
            )
            palette = debug_panel.palette()
            palette.setColor(QPalette.ColorRole.Base, background)
            palette.setColor(QPalette.ColorRole.Text, text_color)
            palette.setColor(
                QPalette.ColorRole.Highlight,
                QColor(self.button_background_color),
            )
            palette.setColor(
                QPalette.ColorRole.HighlightedText,
                QColor(self.button_text_color),
            )
            debug_panel.setPalette(palette)

        log_button = getattr(self, "debug_panel_toggle", None)
        if log_button is not None:
            log_button.setStyleSheet(
                "QPushButton {"
                f" background-color: {self.button_background_color};"
                f" color: {self.button_text_color};"
                f" border: 1px solid {self.graph_grid_color};"
                " padding: 3px 6px;"
                "}"
                "QPushButton:checked {"
                f" background-color: {self.combo_background_color};"
                f" color: {self.combo_text_color};"
                "}"
            )

        if hasattr(self, "main_distribution_selector"):
            self.main_distribution_selector.set_display_colors(
                self.pot_value_text_color,
                self.pot_caption_text_color,
                background.name(),
            )

        if hasattr(self, "preset_label"):
            self.preset_label.setStyleSheet(
                f"color: {text_color.name()};"
                "font-weight: bold;"
            )

        if hasattr(self, "main_bias_knob"):
            for knob in (
                self.main_bias_knob,
                self.main_change_knob,
                self.main_interval_knob,
            ):
                knob.set_display_colors(
                    self.pot_value_text_color,
                    self.pot_caption_text_color,
                    background.name(),
                )

        if hasattr(self, "main_range_indicator"):
            self.main_range_indicator.set_text_color(
                self.range_text_color
            )

        for label in getattr(self, "_window_text_labels", []):
            label.setStyleSheet(
                f"background-color: {background.name()};"
                f"color: {text_color.name()};"
            )

    def apply_arrow_colors(self):
        stylesheet = (
            "QPushButton {"
            f"background-color: {self.arrow_background_color};"
            f"color: {self.arrow_text_color};"
            "}"
        )
        selector = getattr(self, "main_distribution_selector", None)
        if selector is not None:
            selector.set_arrow_style(
                self.arrow_background_color,
                self.arrow_text_color,
            )

    def apply_distribution_graph_colors(self):
        selector = getattr(self, "main_distribution_selector", None)
        if selector is not None:
            selector.set_graph_colors(
                self.distribution_graph_background_color,
                self.distribution_graph_text_color,
            )

    def apply_button_colors(self):
        stylesheet = (
            "QPushButton {"
            f"background-color: {self.button_background_color};"
            f"color: {self.button_text_color};"
            "}"
        )
        for button in (
            getattr(self, "preferences_button", None),
            getattr(self, "main_preset_help_button", None),
            getattr(self, "randomizer_start_button", None),
        ):
            if button is not None:
                button.setStyleSheet(stylesheet)

    def set_window_text_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.apply_window_text_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_pot_text_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.apply_window_text_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_range_text_color(self, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        self.range_text_color = color.name()
        if hasattr(self, "main_range_indicator"):
            self.main_range_indicator.set_text_color(
                self.range_text_color
            )
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_arrow_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.apply_arrow_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_distribution_graph_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.apply_distribution_graph_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_button_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.apply_button_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def apply_combo_colors(self):
        stylesheet = (
            "QComboBox {"
            f"background-color: {self.combo_background_color};"
            f"color: {self.combo_text_color};"
            "}"
            "QComboBox QAbstractItemView {"
            f"background-color: {self.combo_background_color};"
            f"color: {self.combo_text_color};"
            f"selection-color: {self.combo_text_color};"
            "}"
        )
        for widget in QApplication.allWidgets():
            if isinstance(widget, QComboBox):
                widget.setStyleSheet(stylesheet)

    def set_combo_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        self.apply_combo_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_active_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return

        setattr(self, attribute_name, color.name())
        self.update_active_status_colors()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def update_active_status_colors(self):
        for widget in getattr(self, "channel_widgets", []):
            if getattr(widget, "midi_active", False):
                widget.update_active_status()

    def poll_midi_activity(self):
        counts = self.backend.take_channel_activity()

        # The main window is now the randomizer graph, not the former
        # 16-channel indicator grid. Keep the existing activity polling for
        # diagnostics/debug logging, but do not address removed channel widgets.
        for channel, count in enumerate(counts):
            if count > 0:
                self.debug_log(
                    f"RND PAN | MIDI activity: CH {channel + 1} "
                    f"({count} event(s))"
                )

    def clear_midi_activity(self):
        pass

    def clamp_size(self, size):
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = DEFAULT_SIZE

        return max(
            MIN_SIZE,
            min(MAX_SIZE, size),
        )

    def load_size(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_SIZE

        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return self.clamp_size(
                data.get("size", DEFAULT_SIZE)
            )
        except (OSError, ValueError, TypeError):
            return DEFAULT_SIZE

    def save_size(self, size):
        self.window_size = max(self.width(), self.height(), self.window_size)
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_resizable(self):
        # Resizing is intrinsic to the main window, matching RND Velocity.
        # Ignore the legacy fixed-size preference so an old settings file
        # cannot silently lock the PAN window to one size.
        return True

    def load_channel_labels(self):
        if not PREFERENCES_FILE.exists():
            return True

        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return bool(
                data.get("show_channel_labels", True)
            )
        except (OSError, ValueError, TypeError):
            return True

    def set_channel_labels_visible(self, visible):
        self.show_channel_labels = bool(visible)

        for widget in self.channel_widgets:
            widget.channel_label.setVisible(
                self.show_channel_labels
            )

        # When labels are enabled, immediately apply the color selected
        # in Preferences. Visibility alone does not apply the stylesheet
        # because newly created labels initially have only bold styling.
        # Recalculate the grid's required height immediately. Hiding the
        # labels removes their vertical footprint; showing them adds it back.
        QTimer.singleShot(
            0,
            lambda: self.ensure_layout_content_size(
                changed_width=True,
                changed_height=False,
            ),
        )

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def update_channel_label_colors(self):
        color = QColor(self.channel_label_color)
        if not color.isValid():
            color = QColor("#ffffff")
            self.channel_label_color = color.name()

        for widget in self.channel_widgets:
            widget.channel_label.setStyleSheet(
                f"font-weight: bold; color: {color.name()};"
            )
            # Force the visible label to repaint immediately while the
            # Preferences window remains open.
            widget.channel_label.update()
            widget.channel_label.repaint()

        self.update()

    def apply_background_color(self):
        color = QColor(self.background_color)
        if not color.isValid():
            color = QColor("#000000")
            self.background_color = color.name()

        self.central_widget.setStyleSheet(
            f"QWidget {{ background-color: {color.name()}; }}"
        )

    def load_color_preference(self, key, default):
        if not PREFERENCES_FILE.exists():
            return default
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(encoding="utf-8")
            )
            color = QColor(data.get(key, default))
            return color.name() if color.isValid() else default
        except (OSError, ValueError, TypeError):
            return default

    def set_popup_color(self, attribute_name, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        setattr(self, attribute_name, color.name())
        for widget in self.channel_widgets:
            if widget.midi_active:
                widget.update_active_status()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_active_status_text(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_ACTIVE_STATUS_TEXT
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            value = data.get(
                "active_status_text",
                DEFAULT_ACTIVE_STATUS_TEXT,
            )
            if not isinstance(value, str) or not value:
                return DEFAULT_ACTIVE_STATUS_TEXT
            return value
        except (OSError, ValueError, TypeError):
            return DEFAULT_ACTIVE_STATUS_TEXT

    def set_active_status_text(self, text):
        if text is None:
            text = DEFAULT_ACTIVE_STATUS_TEXT

        text = str(text)

        # Keep the field usable even if the user temporarily clears it.
        self.active_status_text = text

        for widget in self.channel_widgets:
            if (
                self.show_active_status
                and widget.midi_active
            ):
                widget.update_active_status()

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_window_width(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_WINDOW_WIDTH
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return max(
                MIN_SIZE,
                min(
                    MAX_SIZE,
                    int(
                        data.get(
                            "window_width",
                            DEFAULT_WINDOW_WIDTH,
                        )
                    ),
                ),
            )
        except (OSError, ValueError, TypeError):
            return DEFAULT_WINDOW_WIDTH

    def layout_minimum_dimensions(self, layout_mode=None):
        """Return practical minimum window dimensions for the selected layout."""
        if layout_mode is None:
            layout_mode = self.layout_mode

        rows, columns, _label = LAYOUTS.get(
            layout_mode,
            LAYOUTS[DEFAULT_LAYOUT],
        )

        # Keep the familiar 120 px minimum on the main dimension, while
        # allowing very wide/tall layouts to become compact in their short
        # dimension. This prevents 1x16 horizontal from becoming an
        # unnecessarily tall 250x120 window.
        min_led = 6
        label_height = 0
        cell_height = min_led + label_height + 2

        if columns > rows:
            minimum_width = MIN_SIZE
            minimum_height = max(24, rows * cell_height)
        elif rows > columns:
            minimum_width = max(24, columns * cell_height)
            minimum_height = MIN_SIZE
        else:
            minimum_width = MIN_SIZE
            minimum_height = MIN_SIZE

        return minimum_width, minimum_height

    def set_window_width(self, width):
        try:
            width = int(width)
        except (TypeError, ValueError):
            return

        width = max(MIN_SIZE, min(MAX_SIZE, width))

        ratio = self.layout_aspect_ratio()
        minimum_width, minimum_height = self.layout_minimum_dimensions()

        width = max(minimum_width, width)
        height = int(round(width / ratio))
        height = max(minimum_height, height)

        # Window Width is authoritative. For extreme layouts such as
        # 1x16 horizontal, the short dimension may need a practical minimum;
        # that must never silently alter the width entered by the user.
        width = min(MAX_SIZE, width)
        height = min(MAX_SIZE, height)

        width, height = self.fit_geometry_to_screen(
            width,
            height,
        )

        if width <= 0 or height <= 0:
            return

        self.window_width = width

        self._auto_layout_resize = True
        try:
            self.setMinimumSize(QSize(1, 1))
            self.setMaximumSize(QSize(MAX_SIZE, MAX_SIZE))
            self.resize(width, height)
        finally:
            self._auto_layout_resize = False

        self.keep_window_on_screen()

        self.window_width = self.width()

        if not self.window_resizable:
            self.setMinimumSize(self.size())
            self.setMaximumSize(self.size())
        else:
            min_width, min_height = self.layout_minimum_dimensions()
            self.setMinimumSize(
                QSize(min_width, min_height)
            )
            self.setMaximumSize(
                QSize(MAX_SIZE, MAX_SIZE)
            )

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_active_status(self):
        if not PREFERENCES_FILE.exists():
            return True
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return bool(
                data.get("show_active_status", True)
            )
        except (OSError, ValueError, TypeError):
            return True

    def set_active_status_visible(self, visible):
        self.show_active_status = bool(visible)

        for widget in self.channel_widgets:
            if self.show_active_status and widget.midi_active:
                widget.update_active_status()
            else:
                widget.active_status_label.hide()

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_rnd_value_size(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_RND_VALUE_SIZE
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return max(
                10,
                min(
                    100,
                    int(
                        data.get(
                            "rnd_value_size",
                            DEFAULT_RND_VALUE_SIZE,
                        )
                    ),
                ),
            )
        except (OSError, ValueError, TypeError):
            return DEFAULT_RND_VALUE_SIZE

    def load_show_current_rnd_value(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_SHOW_CURRENT_RND_VALUE
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return bool(
                data.get(
                    "show_current_rnd_value",
                    DEFAULT_SHOW_CURRENT_RND_VALUE,
                )
            )
        except (OSError, ValueError, TypeError):
            return DEFAULT_SHOW_CURRENT_RND_VALUE

    def load_graph_beats(self):
        if not PREFERENCES_FILE.exists():
            return DEFAULT_GRAPH_BEATS
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return max(
                1,
                min(
                    GRAPH_MAX_POINTS,
                    int(
                        data.get(
                            "graph_beats",
                            DEFAULT_GRAPH_BEATS,
                        )
                    ),
                ),
            )
        except (OSError, ValueError, TypeError):
            return DEFAULT_GRAPH_BEATS

    def set_rnd_value_size(self, size):
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = DEFAULT_RND_VALUE_SIZE
        self.rnd_value_size = max(10, min(100, size))
        if hasattr(self, "randomizer_graph"):
            self.randomizer_graph.set_rnd_value_size(
                self.rnd_value_size
            )
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_show_current_rnd_value(self, enabled):
        self.show_current_rnd_value = bool(enabled)
        if hasattr(self, "randomizer_graph"):
            self.randomizer_graph.set_show_current_rnd_value(
                self.show_current_rnd_value
            )
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_rnd_value_color(self, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return
        self.rnd_value_color = color.name()
        if hasattr(self, "randomizer_graph"):
            self.randomizer_graph.set_rnd_value_color(
                self.rnd_value_color
            )
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def set_graph_beats(self, beats):
        try:
            beats = int(beats)
        except (TypeError, ValueError):
            beats = DEFAULT_GRAPH_BEATS

        beats = max(
            1,
            min(
                GRAPH_MAX_POINTS,
                beats,
            ),
        )
        self.graph_beats = beats

        if hasattr(self, "randomizer_graph"):
            self.randomizer_graph.set_max_points(beats)

        preferences_dialog = getattr(
            self,
            "_preferences_dialog",
            None,
        )
        if preferences_dialog is not None:
            preferences_dialog.sync_graph_beats(beats)

        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_reset_graph_on_left_click(self):
        if not PREFERENCES_FILE.exists():
            return True
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return bool(
                data.get(
                    "reset_graph_on_left_click",
                    True,
                )
            )
        except (OSError, ValueError, TypeError):
            return True

    def set_reset_graph_on_left_click(self, enabled):
        self.reset_graph_on_left_click = bool(enabled)
        if hasattr(self, "randomizer_graph"):
            self.randomizer_graph.set_reset_on_left_click(
                self.reset_graph_on_left_click
            )
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_frameless_window(self):
        if not PREFERENCES_FILE.exists():
            return False
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return bool(
                data.get(
                    "frameless_window",
                    False,
                )
            )
        except (OSError, ValueError, TypeError):
            return False

    def load_color_collection(self):
        try:
            data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
            name = str(data.get("color_collection", "Default"))
            return name if name in (*COLOR_COLLECTIONS.keys(), "Custom") else "Default"
        except (OSError, ValueError, TypeError):
            return "Default"

    def load_debug_to_terminal(self):
        if not PREFERENCES_FILE.exists():
            return False
        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            return bool(data.get("debug_to_terminal", False))
        except (OSError, ValueError, TypeError):
            return False

    def set_frameless_window_preference(self, enabled):
        enabled = bool(enabled)
        if enabled == self._frameless:
            self.save_preferences(
                self.window_size,
                self.window_resizable,
            )
            return

        self.toggle_frameless_window(enabled)

    def set_debug_to_terminal(self, enabled):
        self.debug_to_terminal = bool(enabled)
        if hasattr(self.backend, "set_debug_to_terminal"):
            self.backend.set_debug_to_terminal(
                self.debug_to_terminal
            )
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_channel_label_color(self):
        if not PREFERENCES_FILE.exists():
            return "#b3ffb9"

        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            color = QColor(
                data.get("channel_label_color", "#b3ffb9")
            )
            return color.name() if color.isValid() else "#b3ffb9"
        except (OSError, ValueError, TypeError):
            return "#b3ffb9"

    def set_channel_label_color(self, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return

        self.channel_label_color = color.name()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_background_color(self):
        if not PREFERENCES_FILE.exists():
            return "#000000"

        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(
                    encoding="utf-8"
                )
            )
            color = QColor(data.get("background_color", "#000000"))
            return color.name() if color.isValid() else "#000000"
        except (OSError, ValueError, TypeError):
            return "#000000"

    def set_background_color(self, color_name):
        color = QColor(color_name)
        if not color.isValid():
            return

        self.background_color = color.name()
        self.apply_background_color()
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def load_randomizer_settings(self):
        """Load the saved custom randomizer state from the preferences file."""
        if not PREFERENCES_FILE.exists():
            randomizer.set_range(DEFAULT_RANDOM_MIN, DEFAULT_RANDOM_MAX)
            return

        try:
            data = json.loads(
                PREFERENCES_FILE.read_text(encoding="utf-8")
            )
        except (OSError, ValueError, TypeError):
            randomizer.set_range(DEFAULT_RANDOM_MIN, DEFAULT_RANDOM_MAX)
            return

        try:
            minimum = int(data.get(
                "randomizer_minimum",
                DEFAULT_RANDOM_MIN,
            ))
            maximum = int(data.get(
                "randomizer_maximum",
                DEFAULT_RANDOM_MAX,
            ))
            minimum = max(MIDI_MIN, min(MIDI_MAX, minimum))
            maximum = max(MIDI_MIN, min(MIDI_MAX, maximum))
            if minimum > maximum:
                minimum, maximum = maximum, minimum

            randomizer.set_range(minimum, maximum)

            distribution = data.get(
                "randomizer_distribution",
                randomizer.distribution,
            )
            valid = {key for key, _label in MidiRandomizer.DISTRIBUTIONS}
            if distribution in valid:
                randomizer.set_distribution(distribution)

            randomizer.set_bias(
                int(data.get("randomizer_bias", randomizer.bias))
            )
            randomizer.set_max_change(
                int(data.get(
                    "randomizer_max_change",
                    randomizer.max_change,
                ))
            )
            randomizer.set_prevent_duplicates(
                bool(data.get(
                    "randomizer_prevent_duplicates",
                    randomizer.prevent_duplicates,
                ))
            )
            randomizer.set_avoid_recent(
                bool(data.get(
                    "randomizer_avoid_recent",
                    randomizer.avoid_recent,
                )),
                int(data.get(
                    "randomizer_recent_history",
                    randomizer.recent_history,
                )),
            )
            randomizer.set_interval(
                int(data.get(
                    "randomizer_interval_ms",
                    randomizer.interval_ms,
                ))
            )
            randomizer.set_humanize(
                int(data.get(
                    "randomizer_humanize",
                    randomizer.humanize,
                ))
            )
        except (TypeError, ValueError):
            randomizer.set_range(DEFAULT_RANDOM_MIN, DEFAULT_RANDOM_MAX)

    def persist_randomizer_settings(self):
        """Persist the current randomizer controls as custom settings."""
        self.save_preferences(
            self.window_size,
            self.window_resizable,
        )

    def save_preferences(self, size, resizable):
        try:
            PREFERENCES_FILE.write_text(
                json.dumps(
                    {
                        "size": self.clamp_size(size),
                        "allow_mouse_resize": bool(resizable),
                        "layout": self.layout_mode,
                        "show_graph": bool(self.show_graph),
                        "show_controls": bool(self.show_controls),
                        "show_interval": bool(self.show_interval),
                        "start_in_play": bool(self.start_in_play),
                        "window_width": int(self.width()),
                        "background_color": self.background_color,
                        "color_collection": self.color_collection,
                        "button_background_color": self.button_background_color,
                        "button_text_color": self.button_text_color,
                        "combo_background_color": self.combo_background_color,
                        "combo_text_color": self.combo_text_color,
                        "graph_background_color": self.graph_background_color,
                        "graph_text_color": self.graph_text_color,
                        "window_text_background_color": (
                            self.window_text_background_color
                        ),
                        "window_text_color": self.window_text_color,
                        "pot_value_text_color": self.pot_value_text_color,
                        "pot_caption_text_color": self.pot_caption_text_color,
                        "range_text_color": self.range_text_color,
                        "arrow_background_color": self.arrow_background_color,
                        "arrow_text_color": self.arrow_text_color,
                        "distribution_graph_background_color": (
                            self.distribution_graph_background_color
                        ),
                        "distribution_graph_text_color": (
                            self.distribution_graph_text_color
                        ),
                        "reset_graph_on_left_click": bool(
                            self.reset_graph_on_left_click
                        ),
                        "graph_beats": int(self.graph_beats),
                        "show_current_rnd_value": bool(
                            self.show_current_rnd_value
                        ),
                        "rnd_value_color": self.rnd_value_color,
                        "rnd_value_size": int(
                            self.rnd_value_size
                        ),
                        "debug_to_terminal": bool(self.debug_to_terminal),
                        "open_terminal_for_debug": bool(self.open_terminal_for_debug),
                        "debug_panel_rows": int(self.debug_panel_rows),
                        "frameless_window": bool(
                            self._frameless
                        ),
                        "randomizer_minimum": int(randomizer.minimum),
                        "randomizer_maximum": int(randomizer.maximum),
                        "randomizer_distribution": randomizer.distribution,
                        "randomizer_bias": int(randomizer.bias),
                        "randomizer_max_change": int(randomizer.max_change),
                        "randomizer_prevent_duplicates": bool(
                            randomizer.prevent_duplicates
                        ),
                        "randomizer_avoid_recent": bool(
                            randomizer.avoid_recent
                        ),
                        "randomizer_recent_history": int(
                            randomizer.recent_history
                        ),
                        "randomizer_interval_ms": int(
                            randomizer.interval_ms
                        ),
                        "randomizer_humanize": int(
                            randomizer.humanize
                        ),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            self.debug_log(
                "Preferences save failed: "
                f"{exc}"
            )

    def keep_window_on_screen(self):
        screen = self.screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        geometry = self.geometry()

        if (
            geometry.width() > available.width()
            or geometry.height() > available.height()
        ):
            width, height = self.fit_geometry_to_screen(
                geometry.width(),
                geometry.height(),
            )
            geometry.setSize(QSize(width, height))

        if geometry.top() < available.top():
            geometry.moveTop(available.top())

        if geometry.bottom() > available.bottom():
            geometry.moveTop(
                max(
                    available.top(),
                    available.bottom() - geometry.height() + 1,
                )
            )

        if geometry.left() < available.left():
            geometry.moveLeft(available.left())

        if geometry.right() > available.right():
            geometry.moveLeft(
                max(
                    available.left(),
                    available.right() - geometry.width() + 1,
                )
            )

        self.setGeometry(geometry)

    def apply_resize_mode(self):
        ratio = self.layout_aspect_ratio()

        if self.window_resizable:
            self.setMinimumSize(1, 1)
            self.setMaximumSize(MAX_SIZE, MAX_SIZE)

            short_side = max(MIN_SIZE, self.window_size)
            if ratio >= 1.0:
                width = int(round(short_side * ratio))
                height = short_side
            else:
                width = short_side
                height = int(round(short_side / ratio))

            long_side = max(width, height)
            if long_side > MAX_SIZE:
                scale = MAX_SIZE / long_side
                width = int(round(width * scale))
                height = int(round(height * scale))

            width, height = self.fit_geometry_to_screen(width, height)

            self.resize(width, height)
            self.keep_window_on_screen()
        else:
            if ratio >= 1.0:
                width = int(round(self.window_size * ratio))
                height = self.window_size
            else:
                width = self.window_size
                height = int(round(self.window_size / ratio))

            width, height = self.fit_geometry_to_screen(width, height)

            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)
            self.resize(width, height)
            self.keep_window_on_screen()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

        if (
            self.window_resizable
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.save_preferences(
                self.window_size,
                self.window_resizable,
            )

    def ensure_layout_content_size(self, changed_width=True, changed_height=True):
        """Keep the grid maximized when a single window edge is dragged."""
        if self._resizing_layout or self._auto_layout_resize:
            return

        rows, columns, _label = LAYOUTS.get(
            self.layout_mode,
            LAYOUTS[DEFAULT_LAYOUT],
        )

        label_factor = 0.0
        vertical_overhead = 0

        frame_width = max(1, self.width())
        frame_height = max(1, self.height())

        # If only one edge changed, derive the companion dimension from that
        # edge. This is what makes left/right and top/bottom native resizing
        # useful instead of letting the layout immediately cancel the drag.
        if changed_width and not changed_height:
            cell_width = frame_width / max(1, columns)
            required_cell_height = (
                cell_width * (1.0 + label_factor)
                + vertical_overhead
            )
            target_width = frame_width
            target_height = int(round(rows * required_cell_height))

        elif changed_height and not changed_width:
            usable_cell_height = max(
                1.0,
                frame_height / max(1, rows) - vertical_overhead,
            )
            required_cell_width = (
                usable_cell_height / (1.0 + label_factor)
            )
            target_width = int(round(columns * required_cell_width))
            target_height = frame_height

        else:
            # Corner resize: retain the user's two-dimensional resize and
            # only enlarge a missing companion dimension if needed.
            cell_width = frame_width / max(1, columns)
            required_height = int(round(
                rows * (
                    cell_width * (1.0 + label_factor)
                    + vertical_overhead
                )
            ))

            usable_cell_height = max(
                1.0,
                frame_height / max(1, rows) - vertical_overhead,
            )
            required_width = int(round(
                columns * (
                    usable_cell_height / (1.0 + label_factor)
                )
            ))

            target_width = max(frame_width, required_width)
            target_height = max(frame_height, required_height)

        target_width, target_height = self.fit_geometry_to_screen(
            target_width,
            target_height,
        )

        if (
            target_width == frame_width
            and target_height == frame_height
        ):
            return

        self._auto_layout_resize = True
        try:
            self.resize(target_width, target_height)
            self.keep_window_on_screen()
        finally:
            self._auto_layout_resize = False

    def resizeEvent(self, event):
        if self._resizing_layout:
            super().resizeEvent(event)
            return

        old_width = getattr(self, "_last_resize_width", self.width())
        old_height = getattr(self, "_last_resize_height", self.height())

        width_changed = self.width() != old_width
        height_changed = self.height() != old_height

        self._last_resize_width = self.width()
        self._last_resize_height = self.height()

        preferences_dialog = getattr(
            self,
            "_preferences_dialog",
            None,
        )
        if preferences_dialog is not None:
            preferences_dialog.sync_window_width(
                self.width()
            )

        if self.window_resizable and not self._auto_layout_resize:
            self.window_size = max(
                self.width(),
                self.height(),
            )

            # Defer the companion resize until Qt has completed the native
            # edge/corner resize event. This keeps side and bottom/top edges
            # responsive instead of fighting the window manager mid-drag.
            QTimer.singleShot(
                0,
                lambda w=width_changed, h=height_changed:
                    self.ensure_layout_content_size(w, h),
            )

        super().resizeEvent(event)

        QTimer.singleShot(
            0,
            self._update_main_knob_sizes,
        )
        QTimer.singleShot(
            0,
            self._update_compact_control_labels,
        )

    def set_window_size(self, size):
        size = self.clamp_size(size)
        self.window_size = size
        self.apply_resize_mode()

    def open_preferences(self):
        dialog = PreferencesDialog(
            self.backend,
            self.window_size,
            self.default_size,
            self.window_resizable,
            self.layout_mode,
            self.width(),
            self.background_color,
            self.button_background_color,
            self.button_text_color,
            self.combo_background_color,
            self.combo_text_color,
            self.graph_background_color,
            self.graph_text_color,
            self.graph_grid_color,
            self.graph_axis_color,
            self.graph_point_color,
            self.window_text_background_color,
            self.window_text_color,
            self.pot_value_text_color,
            self.pot_caption_text_color,
            self.range_text_color,
            self.arrow_background_color,
            self.arrow_text_color,
            self.distribution_graph_background_color,
            self.distribution_graph_text_color,
            self.reset_graph_on_left_click,
            self.debug_to_terminal,
            self.graph_beats,
            self._frameless,
            self.show_current_rnd_value,
            self.rnd_value_color,
            self.rnd_value_size,
            self.open_terminal_for_debug,
            self.debug_panel_rows,
            self,
        )

        self._preferences_dialog = dialog

        try:
            result = dialog.exec()
        finally:
            self._preferences_dialog = None

        if result != QDialog.DialogCode.Accepted:
            return

        size = dialog.selected_size
        resizable = dialog.selected_resizable

        if size is not None:
            self.window_resizable = bool(resizable)
            self.set_layout_mode(
                dialog.selected_layout
            )
            self.set_window_size(size)
            self.set_window_width(
                dialog.selected_window_width
            )
            self.set_background_color(
                dialog.selected_background_color
            )
            self.set_button_color(
                "button_background_color",
                dialog.selected_button_background_color,
            )
            self.set_button_color(
                "button_text_color",
                dialog.selected_button_text_color,
            )
            self.set_combo_color(
                "combo_background_color",
                dialog.selected_combo_background_color,
            )
            self.set_combo_color(
                "combo_text_color",
                dialog.selected_combo_text_color,
            )
            self.set_pot_text_color(
                "pot_value_text_color",
                dialog.selected_pot_value_text_color,
            )
            self.set_pot_text_color(
                "pot_caption_text_color",
                dialog.selected_pot_caption_text_color,
            )
            self.set_range_text_color(
                dialog.selected_range_text_color,
            )
            self.set_graph_color(
                "graph_background_color",
                dialog.selected_graph_background_color,
            )
            self.set_graph_color(
                "graph_grid_color",
                dialog.selected_graph_grid_color,
            )
            self.set_graph_color(
                "graph_axis_color",
                dialog.selected_graph_axis_color,
            )
            self.set_graph_color(
                "graph_text_color",
                dialog.selected_graph_text_color,
            )
            self.set_graph_color(
                "graph_point_color",
                dialog.selected_graph_point_color,
            )
            self.set_reset_graph_on_left_click(
                dialog.selected_reset_graph_on_left_click
            )
            self.set_debug_to_terminal(
                dialog.selected_debug_to_terminal
            )
            self.set_graph_beats(
                dialog.selected_graph_beats
            )
            if dialog.selected_frameless_window != self._frameless:
                self.toggle_frameless_window(
                    dialog.selected_frameless_window
                )
            else:
                self.save_preferences(
                    size,
                    self.window_resizable,
                )

    def reset_all_preferences(self):
        """Restore every persisted application preference to its default."""
        self.window_resizable = False
        self.layout_mode = DEFAULT_LAYOUT
        self.reset_graph_on_left_click = True
        self.debug_to_terminal = False
        self.graph_beats = DEFAULT_GRAPH_BEATS
        self.show_current_rnd_value = DEFAULT_SHOW_CURRENT_RND_VALUE
        self.rnd_value_color = DEFAULT_RND_VALUE_COLOR
        self.rnd_value_size = DEFAULT_RND_VALUE_SIZE
        self._frameless = False

        preferences_dialog = getattr(
            self,
            "_preferences_dialog",
            None,
        )
        display_page = (
            getattr(preferences_dialog, "display_page", None)
            if preferences_dialog is not None
            else None
        )
        if display_page is not None:
            display_page.frameless_checkbox.setChecked(False)
            display_page.current_rnd_checkbox.setChecked(
                DEFAULT_SHOW_CURRENT_RND_VALUE
            )
            display_page.rnd_value_size_spin.setValue(
                DEFAULT_RND_VALUE_SIZE
            )
            display_page.debug_checkbox.setChecked(False)

        self.background_color = "#000000"
        self.button_background_color = DEFAULT_BUTTON_BACKGROUND_COLOR
        self.button_text_color = DEFAULT_BUTTON_TEXT_COLOR
        self.combo_background_color = DEFAULT_COMBO_BACKGROUND_COLOR
        self.combo_text_color = DEFAULT_COMBO_TEXT_COLOR
        self.window_text_background_color = DEFAULT_WINDOW_TEXT_BACKGROUND_COLOR
        self.window_text_color = DEFAULT_WINDOW_TEXT_COLOR
        self.pot_value_text_color = DEFAULT_POT_VALUE_TEXT_COLOR
        self.pot_caption_text_color = DEFAULT_POT_CAPTION_TEXT_COLOR
        self.range_text_color = DEFAULT_RANGE_TEXT_COLOR
        self.arrow_background_color = DEFAULT_ARROW_BACKGROUND_COLOR
        self.arrow_text_color = DEFAULT_ARROW_TEXT_COLOR
        self.distribution_graph_background_color = (
            DEFAULT_DISTRIBUTION_GRAPH_BACKGROUND_COLOR
        )
        self.distribution_graph_text_color = (
            DEFAULT_DISTRIBUTION_GRAPH_TEXT_COLOR
        )
        self.graph_background_color = DEFAULT_GRAPH_BACKGROUND
        self.graph_grid_color = DEFAULT_GRAPH_GRID_COLOR
        self.graph_axis_color = DEFAULT_GRAPH_AXIS_COLOR
        self.graph_text_color = DEFAULT_GRAPH_TEXT_COLOR
        self.graph_point_color = DEFAULT_GRAPH_POINT_COLOR

        self.window_size = DEFAULT_SIZE
        self.window_width = DEFAULT_WINDOW_WIDTH

        # Restore the recommended MIDI activity filter.
        if hasattr(self.backend, "recommended_activity_filter"):
            self.backend.activity_filter = dict(
                self.backend.recommended_activity_filter
            )

        if hasattr(self.backend, "set_debug_to_terminal"):
            self.backend.set_debug_to_terminal(False)

        self.rebuild_channel_layout()
        self.apply_background_color()
        self.apply_button_colors()
        self.apply_combo_colors()
        self.apply_window_text_colors()
        self.apply_arrow_colors()
        self.apply_distribution_graph_colors()
        self.randomizer_graph.set_colors(
            self.graph_background_color,
            self.graph_grid_color,
            self.graph_axis_color,
            self.graph_text_color,
            self.graph_point_color,
        )
        self.randomizer_graph.set_reset_on_left_click(
            self.reset_graph_on_left_click
        )
        self.randomizer_graph.setToolTip(
            wrapped_tooltip(
                "Randomizer Graph\n"
                "Shows generated MIDI values in chronological order.\n"
                "Values generated by TEST and real Note On events "
                "are both displayed.\n"
                "Clear-on-left-click can be enabled in Display settings."
            )
        )
        self.clear_randomizer_graph()

        self.apply_resize_mode()

        preferences_dialog = getattr(
            self,
            "_preferences_dialog",
            None,
        )
        if preferences_dialog is not None:
            preferences_dialog.sync_layout_settings(
                DEFAULT_LAYOUT,
                False,
            )
            preferences_dialog.sync_window_width(
                self.width(),
            )

        self.save_preferences(
            DEFAULT_SIZE,
            False,
        )

    def request_quit(self):
        answer = QMessageBox.question(
            self,
            "Quit MIDI Randomize",
            "Are you sure you want to quit MIDI Randomize?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.close()

    def show_help(self):
        QMessageBox.information(
            self,
            "MIDI Randomize Help",
            "RND PAN\n\n"
            "A MIDI Randomize variant that uses incoming Note On events "
            "as the trigger for randomized Pan (MIDI CC10).\n\n"
            "The signal path is:\n"
            "  MIDI source -> RND PAN -> MIDI destination\n\n"
            "On a Note On, the original Note On is forwarded unchanged and "
            "a separate CC10 Pan event is emitted on the same MIDI channel "
            "and JACK event time.\n\n"
            "Serial connection:\n"
            "  MIDI source -> RND PAN -> RND VEL -> destination\n"
            "  Each MIDI event passes through the chain once. RND PAN adds "
            "its CC10 Pan event; RND VEL then modifies the Note On velocity. "
            "This does not duplicate the Note On.\n\n"
            "Parallel connection:\n"
            "  MIDI source -> RND PAN -> destination\n"
            "             -> RND VEL -> destination\n"
            "  Both processors receive the same original Note On. If both "
            "branches are connected to the same destination, the original "
            "and modified Note On events can reach the destination as "
            "separate events. For a combined processing chain, use a serial "
            "connection.\n\n"
            "Terminal event format:\n"
            "  [HH:MM:SS.mmm] CH 8  A0  PAN 64 → 91\n"
            "  The timestamp-free event body is the intended RaySession "
            "integration format:\n"
            "  CH 8  A0  PAN 64 → 91\n\n"
            "Preferences / MIDI Filter:\n"
            "  Select which MIDI message types pass through the filter.\n\n"
            "Preferences / Randomizer Behavior:\n"
            "  Configure the PAN randomization range, distribution, Bias, "
            "Max. Change, duplicate/recent-value behavior and timing controls.\n\n"
            "Main-window Width — mirror behaviour:\n"
            "  Speed changes the width of the active PAN interval while "
            "keeping its center fixed. The interval expands or contracts "
            "toward the 0–127 limits. The Preferences Minimum/Maximum "
            "values remain the base interval.\n\n"
            "  The interval indicator below the main knobs is also editable: "
            "drag either endpoint to change Minimum/Maximum directly. "
            "The Preferences values, main window and saved Custom settings "
            "stay synchronized in real time.\n\n"
            "Preferences / Display:\n"
            "  Configure the existing MIDI Randomize display and terminal "
            "debug behavior."
        )

    def closeEvent(self, event):
        if hasattr(self, "generated_value_timer"):
            self.generated_value_timer.stop()

        if self._replacing_window:
            event.accept()
            return

        if self._close_confirmed:
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            APP_TITLE,
            "Closing this window will stop the MIDI Patchbay "
            "JACK client and disconnect its MIDI ports.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        self.save_size(self.window_size)

        if (
            hasattr(self, "_midi_monitor")
            and self._midi_monitor is not None
        ):
            self._midi_monitor.close()
            self._midi_monitor = None

        if hasattr(self, "activity_timer"):
            self.activity_timer.stop()
        if hasattr(self, "activity_clear_timer"):
            self.activity_clear_timer.stop()
        if hasattr(self, "randomizer_timer"):
            self.stop_randomizer()

        self.backend.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(
        APP_TITLE
    )

    try:
        window = MidiRandomizeWindow()
    except jack.JackError as exc:
        QMessageBox.critical(
            None,
            APP_TITLE,
            "Could not connect to the JACK/PipeWire MIDI server.\n\n"
            f"{exc}",
        )
        return 1
    except Exception as exc:
        QMessageBox.critical(
            None,
            APP_TITLE,
            "Could not start the MIDI Patchbay.\n\n"
            f"{exc}",
        )
        return 1

    app._midi_randomize_window = window
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
