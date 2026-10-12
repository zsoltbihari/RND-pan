# RND PAN

A real-time JACK/PipeWire MIDI utility that adds randomized stereo-pan automation to incoming notes. RND PAN forwards incoming MIDI events and, while PLAY is active, generates a separate MIDI Control Change 10 (Pan) message in response to incoming Note On events.

> **Important:** TEST is a visual/randomizer test only. It does not send MIDI output. Actual MIDI processing is active only in PLAY mode.

---

# English Manual

## 1. Overview

RND PAN is designed for Linux audio systems using JACK or PipeWire's JACK compatibility layer. It provides a compact GUI for randomizing MIDI pan values while keeping the original note event available to the rest of the MIDI chain.

- Receives MIDI from a selectable JACK/PipeWire MIDI input port.
- Sends MIDI to a selectable JACK/PipeWire MIDI output port.
- When PLAY is active, reacts to incoming Note On events by generating a separate CC10 Pan event on the same MIDI channel.
- Supports 16 MIDI channels.
- Offers multiple random distributions, bias, maximum-change limits, humanization, duplicate/recent-value avoidance, presets, a graph, and adjustable PAN range controls.
- Saves UI and randomizer preferences in a JSON file.

## 2. Requirements

- Linux with a working JACK server or PipeWire JACK compatibility.
- Python 3.
- PySide6 (Qt for Python).
- `jack-client` Python module (`import jack`). On Debian-based systems, the package may be available as `python3-jack-client`; alternatively install the matching Python package for the interpreter used to run the program.

The MIDI backend and GUI have to run in an environment where the selected Python interpreter can import both `jack` and `PySide6`.

## 3. Installation and launch

Place `rnd-pan.py` and `rnd-pan.sh` in the same directory. Make the launcher executable:

```bash
chmod +x rnd-pan.sh
```

Start the application:

```bash
./rnd-pan.sh start
```

Other launcher commands:

```bash
./rnd-pan.sh status
./rnd-pan.sh stop
./rnd-pan.sh restart
./rnd-pan.sh killall
./rnd-pan.sh log
```

`killall` only targets processes identified as instances of this RND PAN script; it is not a system-wide Python process killer.

You can also launch the GUI directly for troubleshooting:

```bash
python3 ./rnd-pan.py
```

## 4. MIDI routing

1. Start JACK or PipeWire and make sure MIDI ports are available.
2. Open **Preferences → MIDI Input** and select the source port.
3. Open **Preferences → MIDI Output** and select the destination port.
4. Connect the ports using the application's controls or your patchbay.
5. Press **PLAY** to enable processing.
6. Play notes and verify the generated CC10 messages at the destination.

The program's input/output port selection depends on the ports exposed by the current JACK/PipeWire session. A port must exist and be accessible before it can be selected.

### MIDI event behaviour

- Incoming MIDI events are forwarded independently of the PAN randomization logic.
- While PLAY is active, incoming Note On events trigger an additional CC10 Pan message on the same MIDI channel.
- The original Note On event is forwarded; RND PAN does not replace it with a different note message.
- CC10 is intended to be sent before the corresponding Note On so the receiver can apply the pan value as the note starts. Verify the event order and behaviour with your target instrument or MIDI monitor.
- TEST does not send MIDI messages.

### Chaining with RND Velocity

A serial chain can be arranged as:

```text
MIDI source → RND PAN → RND Velocity → MIDI destination
```

RND PAN adds CC10 Pan events and forwards the note events. RND Velocity can then modify Note On velocity. Avoid accidentally routing parallel branches to the same destination if duplicate note events are not desired.

## 5. Main window controls

### Graph and current value

The graph displays recent generated values. The large current-value display can be enabled in Display preferences. Graph point count, current-value size, and clear-on-left-click behaviour are configurable.

### Distribution

The distribution selector chooses how generated values are weighted inside the permitted range:

- **Uniform** — values are approximately equally likely.
- **Center-biased** — values near the centre are more likely.
- **Edge-biased** — values near the range boundaries are more likely.
- **Gaussian** — a bell-shaped distribution favouring the centre.

The distribution preview helps visualize the selected weighting.

### Four rotary controls

- **Bias** — shifts probability toward lower or higher values without changing the Minimum/Maximum boundaries.
- **Max. Change** — limits how far a newly generated value can move from the previous generated value. Unlimited disables this limit.
- **Interval Shift** (shown as **Position** in some parts of the UI) — shifts the whole PAN interval without intentionally changing its width, subject to the MIDI 0–127 limits.
- **Width** — expands or contracts the PAN interval symmetrically around its centre, subject to the MIDI 0–127 limits.

Double-clicking a rotary control restores that control's defined centre/default value. The exact value is indicated by the control's tooltip and on-screen value label.

### Minimum and Maximum

The randomizer's allowed output interval is bounded by MIDI values 0–127. The default randomizer range is 13–115; the PAN Randomizer preferences page has a **Reset to MIDI PAN Randomizer** control that restores its recommended interval.

### Humanize and repeat avoidance

- **Humanize** adds a random deviation around the incoming PAN value. The result is clamped to the MIDI 0–127 range.
- **Prevent duplicates** avoids repeating the immediately preceding generated value.
- **Avoid recent values** tries to avoid values in the configured recent-history window.
- **Maximum Change** can constrain step-to-step movement independently of the range.

The precise interaction between Humanize and the other randomization settings follows the program's selected behaviour mode and preset.

### Presets

Presets apply a coordinated group of randomizer settings. Available profiles include:

- **PAN — Default** — balanced, centre-biased profile for general use.
- **PAN — Natural** — controlled movement around the centre.
- **PAN — Wide** — broader stereo movement.
- **PAN — Humanize Soft** — subtle deviation around the input.
- **PAN — Humanize Hard** — stronger deviation around the input.
- **Custom — current settings** — indicates manually adjusted values.

Changing a parameter manually changes the preset selection to Custom. Presets configure randomizer behaviour; they do not change the PLAY/STOP state.

## 6. Preferences

Open Preferences with the gear button.

- **Layouts** — configure the visibility of supported main-window sections, including the graph, knob/distribution controls, and interval display. Options apply immediately and are saved.
- **MIDI Input / MIDI Output** — select available JACK/PipeWire ports.
- **PAN Randomizer** — set the Minimum and Maximum values and restore the recommended PAN interval.
- **Randomization Behavior** — configure distribution, Bias, Maximum Change, Humanize, duplicate/recent-value avoidance, and interval-related behaviour.
- **Display** — configure window dimensions, frameless mode, graph display, current-value display, colours, and debug output.

### Frameless window

Frameless mode removes the native title bar and border. Window movement and edge/corner resizing are handled by the application rather than the window manager. If resizing does not work on a particular desktop environment, turn Frameless mode off and report the desktop/session and the exact behaviour.

### Colour collections

- **Default** — standard high-contrast palette.
- **Matrix** — dark background with green highlights.
- **Zombie** — muted dark green/olive palette.
- **Vampire** — dark burgundy with red/pink highlights.
- **Barbie** — bright pink palette.
- **Custom** — allows individual colour settings.

Colour settings affect multiple UI elements, including the graph, controls, labels, buttons, and log panel. Check text contrast after customizing colours.

## 7. Debug log

The **Log** button expands or collapses the main-window debug panel. The window should expand when the panel is opened and return to its previous height when it is closed.

Display preferences provide:

- **Debug to terminal** — writes debug messages to the launching terminal/process output.
- **Open terminal for debug output** — opens a separate terminal following the debug log file.
- **Main-window debug lines** — selects 2–10 visible lines in the main-window panel.

The application's debug file is `rnd-pan-debug.log` in the current working directory. The launcher maintains its own process log under `~/.local/state/rnd-pan/rnd-pan.log` (unless `XDG_STATE_HOME` is set). These files serve different purposes: the application debug file is used by the GUI debug feature, while the launcher log captures standard output and errors from the process.

## 8. ALSA MIDI Device Status

The ALSA MIDI Device Status window reads Linux kernel-facing ALSA information exposed under `/proc/asound`. It is a diagnostic view of device/driver state, not a decoder of the live MIDI event stream. Use a MIDI monitor or patchbay to inspect actual MIDI messages.

## 9. Troubleshooting

- **The program exits immediately:** run `python3 ./rnd-pan.py` in a terminal and inspect the error. Confirm `PySide6` and `jack` import successfully.
- **No MIDI ports appear:** start JACK/PipeWire, check the session's MIDI ports, and refresh the port list.
- **No PAN events are produced:** select valid input/output ports and ensure PLAY is active. TEST is not a MIDI output test.
- **The destination receives notes but pan does not change:** confirm the destination responds to MIDI CC10 on the same channel and inspect the output with a MIDI monitor.
- **The UI colours are hard to read:** choose another colour collection or adjust individual colours in Display preferences.
- **Frameless resizing is unavailable:** temporarily disable Frameless window mode and verify resizing with the normal window frame.
- **The launcher reports an already-running instance:** inspect `./rnd-pan.sh status`; use `./rnd-pan.sh killall` only to stop identified RND PAN instances.

## 10. Configuration and logs

- Preferences: `rnd-pan-preferences.json` in the current working directory.
- GUI debug log: `rnd-pan-debug.log` in the current working directory.
- Launcher log: `~/.local/state/rnd-pan/rnd-pan.log` by default.
- PID file: `$XDG_RUNTIME_DIR/rnd-pan/rnd-pan.pid`, or the launcher's fallback runtime directory if `XDG_RUNTIME_DIR` is not set.

Keep the Python script and launcher together. Back up the JSON preferences file before manually editing it.

---

# Magyar kézikönyv

## 1. Áttekintés

Az RND PAN egy Linuxon futó, JACK/PipeWire MIDI-környezethez készült segédprogram. A beérkező hangindításokhoz véletlenszerű sztereó panorámaértékeket rendel. PLAY állapotban a Note On esemény hatására külön MIDI Control Change 10 (Pan) üzenetet generál, miközben az eredeti MIDI-eseményeket továbbítja.

- Választható JACK/PipeWire MIDI-bemenet és -kimenet.
- PLAY állapotban a beérkező Note On események külön CC10 Pan üzenetet váltanak ki ugyanazon a MIDI-csatornán.
- A program 16 MIDI-csatornát támogat.
- Többféle eloszlás, Bias, maximális változás, Humanize, ismétléskerülés, presetek, grafikon és PAN-tartományvezérlés áll rendelkezésre.
- A kezelőfelület és a randomizáló beállításai JSON-fájlban mentődnek.

**Fontos:** a TEST csak a véletlenértéket és a grafikont teszteli, MIDI-üzenetet nem küld. A tényleges MIDI-feldolgozás PLAY állapotban történik.

## 2. Követelmények

- Linux, működő JACK szerverrel vagy PipeWire JACK-kompatibilitással.
- Python 3.
- PySide6 (Qt for Python).
- A `jack` Python-modul (`import jack`). Debian-alapú rendszeren a `python3-jack-client` csomag elérhető lehet; más esetben a használt Python-interpreterhez illő csomagot kell telepíteni.

A programot olyan Python-interpreterrel kell futtatni, amelyből a `jack` és a `PySide6` modul is importálható.

## 3. Telepítés és indítás

Tedd az `rnd-pan.py` és `rnd-pan.sh` fájlokat ugyanabba a könyvtárba, majd tedd futtathatóvá az indítószkriptet:

```bash
chmod +x rnd-pan.sh
```

Indítás:

```bash
./rnd-pan.sh start
```

További parancsok:

```bash
./rnd-pan.sh status
./rnd-pan.sh stop
./rnd-pan.sh restart
./rnd-pan.sh killall
./rnd-pan.sh log
```

A `killall` csak az azonosított RND PAN-példányokat célozza, nem állít le általánosan minden Python-folyamatot.

Hibakereséshez a grafikus program közvetlenül is indítható:

```bash
python3 ./rnd-pan.py
```

## 4. MIDI-útvonal és működés

1. Indítsd el a JACK-et vagy a PipeWire-t, és ellenőrizd, hogy vannak MIDI-portok.
2. Nyisd meg a **Preferences → MIDI Input** oldalt, majd válaszd ki a bemeneti portot.
3. A **Preferences → MIDI Output** oldalon válaszd ki a kimeneti portot.
4. A portokat a programban vagy a patchbayben kösd össze.
5. Nyomd meg a **PLAY** gombot.
6. Játssz le hangokat, és MIDI-monitorral ellenőrizd a kimenő CC10 üzeneteket.

A portválasztó az aktuális JACK/PipeWire-munkamenetben elérhető portokat mutatja. Csak létező és elérhető port választható ki.

### MIDI-események

- A beérkező MIDI-események továbbítása független a PAN-randomizálástól.
- PLAY állapotban a Note On esemény külön CC10 Pan üzenetet vált ki ugyanazon a csatornán.
- Az eredeti Note On továbbhalad, nem helyettesíti másik hangüzenet.
- A CC10 célja, hogy a megfelelő Note On előtt érkezzen meg, így a hangszer már a hang indításakor alkalmazhassa a panorámát. A pontos viselkedést ellenőrizd a használt hangszerrel vagy MIDI-monitorral.
- A TEST nem küld MIDI-üzenetet.

### Összekötés az RND Velocity programmal

Soros lánc például:

```text
MIDI-forrás → RND PAN → RND Velocity → MIDI-cél
```

Az RND PAN CC10 Pan üzeneteket ad hozzá, és továbbítja a hangüzeneteket. Az RND Velocity ezután módosíthatja a Note On velocity értékét. Ha nem szeretnél duplikált hangindításokat, kerüld a párhuzamos ágak azonos kimenetre kötését.

## 5. Főablak és vezérlők

### Grafikon és aktuális érték

A grafikon a legutóbbi generált értékeket mutatja. A nagy aktuálisérték-kijelzés a Display beállításokban kapcsolható be. A grafikon pontszáma, az érték mérete és a bal kattintásra történő törlés is beállítható.

### Eloszlás

- **Uniform** – az értékek közel azonos eséllyel fordulnak elő.
- **Center-biased** – a tartomány közepe felé húz.
- **Edge-biased** – a tartomány szélei felé húz.
- **Gaussian** – haranggörbe jellegű eloszlás, a közép körüli értékek gyakoribbak.

Az eloszlás előnézete segít a súlyozás megértésében.

### Négy forgatógomb

- **Bias** – az alacsonyabb vagy magasabb értékek felé tolja a valószínűséget, de nem módosítja a Minimum/Maximum határokat.
- **Max. Change** – korlátozza, hogy az új érték mennyivel térhet el az előző generált értéktől. Unlimited esetén nincs ilyen korlátozás.
- **Interval Shift / Position** – a PAN-intervallumot tolja el úgy, hogy a szélessége lehetőleg változatlan maradjon, a MIDI 0–127 határain belül.
- **Width** – a PAN-intervallumot a középpont körül szimmetrikusan szélesíti vagy szűkíti, a MIDI 0–127 határain belül.

A forgatógomb dupla kattintása az adott vezérlő alapértelmezett vagy középértékére állítja vissza. A pontos értéket a tooltip és a kijelző mutatja.

### Minimum és Maximum

A generált MIDI-érték 0 és 127 közé esik. Az alapértelmezett randomizálási tartomány 13–115. A PAN Randomizer Preferences oldalon a **Reset to MIDI PAN Randomizer** gomb visszaállítja az ajánlott intervallumot.

### Humanize és ismétléskerülés

- **Humanize** – véletlen eltérést ad a beérkező PAN-érték körül. Az eredmény a MIDI 0–127 tartományban marad.
- **Prevent duplicates** – megpróbálja elkerülni az előző generált érték közvetlen ismétlését.
- **Avoid recent values** – megpróbálja elkerülni az előzményekben szereplő legutóbbi értékeket.
- **Maximum Change** – a tartománytól függetlenül korlátozhatja az egymást követő értékek ugrását.

A Humanize és a többi beállítás pontos együttműködése az aktuális működési módtól és presettől függ.

### Presetek

- **PAN — Default** – kiegyensúlyozott, közép felé húzó alapbeállítás.
- **PAN — Natural** – kontrollált mozgás a közép körül.
- **PAN — Wide** – szélesebb sztereó mozgás.
- **PAN — Humanize Soft** – finom eltérés a bemeneti érték körül.
- **PAN — Humanize Hard** – erőteljesebb eltérés a bemeneti érték körül.
- **Custom — current settings** – a kézzel módosított aktuális beállításokat jelzi.

A paraméterek kézi módosításakor a preset Custom állapotba vált. A presetek a randomizáló viselkedését állítják, a PLAY/STOP állapotot nem változtatják meg.

## 6. Preferences

A fogaskerék gombbal nyitható meg.

- **Layouts** – a főablak részeinek, például a grafikonnak, a potmétereknek/eloszlásválasztónak és az intervallumkijelzésnek a láthatóságát szabályozza. A változtatások azonnal érvényesülnek és mentődnek.
- **MIDI Input / MIDI Output** – JACK/PipeWire-portok kiválasztása.
- **PAN Randomizer** – Minimum és Maximum értékek, valamint az ajánlott PAN-tartomány visszaállítása.
- **Randomization Behavior** – eloszlás, Bias, Maximum Change, Humanize, ismétléskerülés és időzítési beállítások.
- **Display** – ablakméret, frameless mód, grafikon, aktuális érték, színek és debugkimenet.

### Frameless ablak

A frameless mód eltávolítja a címsort és az ablakkeretet. Az ablak mozgatását és széleinél/sarkainál történő méretezését ilyenkor a program kezeli, nem a szokásos ablakkeret. Ha a méretezés az adott asztali környezetben nem működik, kapcsold ki a frameless módot, és jegyezd fel az asztali környezetet és a tapasztalt viselkedést.

### Színpresetek

- **Default** – alapértelmezett, kontrasztos színek.
- **Matrix** – sötét háttér és zöld kiemelések.
- **Zombie** – tompa, sötétzöld/olívás paletta.
- **Vampire** – sötét bordó, vörös és rózsaszín kiemelésekkel.
- **Barbie** – élénk rózsaszín paletta.
- **Custom** – egyedi színek beállítása.

A színbeállítások több felületi elemet érintenek: grafikont, gombokat, címkéket, vezérlőket és naplópanelt. Egyéni színezés után ellenőrizd a szöveg olvashatóságát.

## 7. Debug napló

A **Log** gomb lenyitja vagy becsukja a főablak naplópaneljét. A panel kinyitásakor az ablaknak meg kell nőnie, becsukásakor pedig vissza kell állnia az előző magasságára.

A Display beállításai:

- **Debug to terminal** – a debugüzeneteket az indító terminálra/feladat kimenetére írja.
- **Open terminal for debug output** – külön terminált nyit, amely követi a debugnapló fájlt.
- **Main-window debug lines** – a főablakban látható sorok számát 2–10 között állítja.

Az alkalmazás debugfájlja a munkakönyvtárban található `rnd-pan-debug.log`. Az indítószkript saját naplója alapértelmezésben `~/.local/state/rnd-pan/rnd-pan.log` (vagy a `XDG_STATE_HOME` alatti hely). A két fájl célja különböző: az alkalmazás debugfájlja a GUI naplófunkcióját szolgálja, az indító naplója pedig a program standard kimenetét és hibáit rögzíti.

## 8. ALSA MIDI Device Status

Ez az ablak a Linux ALSA kernel-/illesztőprogram-állapotát mutatja a `/proc/asound` adatai alapján. Nem élő MIDI-eseménydekóder. A tényleges MIDI-üzenetek ellenőrzéséhez használj MIDI-monitort vagy patchbayt.

## 9. Hibakeresés

- **A program azonnal kilép:** indítsd terminálból: `python3 ./rnd-pan.py`. Ellenőrizd, hogy a `PySide6` és a `jack` importálható.
- **Nem jelennek meg MIDI-portok:** indítsd el a JACK/PipeWire rendszert, ellenőrizd a portokat, majd frissítsd a listát.
- **Nem keletkeznek PAN-üzenetek:** válassz érvényes be-/kimenetet, és kapcsold be a PLAY módot. A TEST nem MIDI-kimeneti teszt.
- **A hangok átmennek, de a panoráma nem változik:** ellenőrizd, hogy a hangszer fogadja-e a CC10-et az adott csatornán, és vizsgáld meg a kimenetet MIDI-monitorral.
- **Nehezen olvasható a felület:** válassz másik színpresetet vagy állítsd be egyenként a színeket.
- **Nem méretezhető a frameless ablak:** ideiglenesen kapcsold ki a frameless módot, és próbáld a normál ablakkerettel.
- **Az indító már futó példányt jelez:** futtasd a `./rnd-pan.sh status` parancsot. A `killall` csak az azonosított RND PAN-folyamatokat állítja le.

## 10. Beállításfájlok és naplók

- Beállítások: `rnd-pan-preferences.json` a munkakönyvtárban.
- GUI debugnapló: `rnd-pan-debug.log` a munkakönyvtárban.
- Indítószkript naplója: alapértelmezésben `~/.local/state/rnd-pan/rnd-pan.log`.
- PID-fájl: `$XDG_RUNTIME_DIR/rnd-pan/rnd-pan.pid`, vagy az indítószkript tartalék runtime könyvtára, ha az `XDG_RUNTIME_DIR` nincs beállítva.

Az `rnd-pan.py` és az `rnd-pan.sh` maradjon egy könyvtárban. A JSON-fájl kézi módosítása előtt készíts biztonsági másolatot.
