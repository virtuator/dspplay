# dspplay

`dspplay` ist eine kleine Realtime-Hülle für den Audio-DSP/Python-Kurs. Die Studierenden schreiben weiterhin eine gewöhnliche Funktion

```python
def process(block):
    return 0.5 * block
```

und können deren Wirkung unmittelbar hören. `dspplay` kümmert sich um Audiogerät, Blöcke, WAV-Loop und ein minimales Sliderfenster.

Der Entwurf ist bewusst klein. Er ersetzt weder NumPy noch Soundfile und soll die eigentliche Signalverarbeitung nicht verstecken.

## Installation

Im Ordner `dspplay`:

```bash
uv sync
```

Für die Verwendung aus einem bestehenden Kursprojekt:

```bash
uv add --editable ../dspplay
```

Alternativ kann der Ordner `dspplay` direkt als eigenes PyCharm-Projekt geöffnet werden.

## Erstes Beispiel: Gain auf einem WAV-Loop

Lege zunächst eine kurze Audiodatei unter `audio/drums.wav` ab. Das vollständige Script lautet:

```python
from dspplay import FileLoop, Parameter, show_controls

gain = Parameter("Gain", 0.5, 0.0, 2.0)


def process(block):
    return gain.value * block


with FileLoop("audio/drums.wav", process) as player:
    show_controls(gain, title="Gain", check=player.check)
```

Beim Verschieben des Reglers ändert sich `gain.value`. Der nächste Audioblock verwendet bereits den neuen Wert.

## Das Datenmodell

`process()` erhält ein NumPy-Array mit der Form

```text
(frames, channels)
```

Ein Block mit 256 Frames und zwei Kanälen hat also `block.shape == (256, 2)`. Die Funktion muss wieder ein Array derselben Form zurückgeben.

```python
def process(block):
    output = 0.5 * block
    return output
```

Die Audiodaten verwenden `float32`. Der übliche Wertebereich liegt zwischen `-1.0` und `+1.0`. Werte ausserhalb dieses Bereichs können beim Ausgang verzerren oder begrenzt werden.

## Mehrere und logarithmische Parameter

Für Frequenzen ist eine logarithmische Reglerskala sinnvoll:

```python
cutoff = Parameter(
    "Cutoff",
    1_000,
    20,
    20_000,
    scale="log",
    unit="Hz",
    decimals=0,
)
```

Mehrere Parameter werden gemeinsam angezeigt:

```python
show_controls(cutoff, resonance, title="Lowpass")
```

`Parameter` begrenzt den Wert automatisch auf `minimum` bis `maximum`. Eine Parametersprung wird absichtlich nicht automatisch geglättet: Ob und wie geglättet wird, gehört zum DSP-Algorithmus und kann später selbst untersucht werden.

## Live-Eingang

Dieselbe `process()`-Idee funktioniert mit Mikrofon, Gitarre oder Audiointerface:

```python
from dspplay import LiveInput, Parameter, show_controls

gain = Parameter("Gain", 0.25, 0.0, 1.0)


def process(block):
    return gain.value * block


with LiveInput(process, samplerate=48_000, channels=1) as player:
    show_controls(gain, title="Live gain", check=player.check)
```

Beim Live-Betrieb zuerst Kopfhörer und einen niedrigen Ausgangspegel verwenden. Lautsprecher und Mikrofon können unmittelbar eine Rückkopplung erzeugen.

## Audiogeräte auswählen

Die verfügbaren Geräte lassen sich anzeigen mit:

```python
from dspplay import list_devices

list_devices()
```

Danach kann ein Gerätename oder eine Gerätenummer übergeben werden:

```python
FileLoop("audio/drums.wav", process, device="MacBook Pro Speakers")
```

Für getrennte Ein- und Ausgänge:

```python
LiveInput(process, device=(2, 5))
```

## Blockgrösse und Latenz

Der Standardwert ist `blocksize=256`. Bei 48 kHz entspricht ein Block

$$
\frac{256}{48\,000} \approx 5.3\,\text{ms}.
$$

Das ist nur ein Teil der gesamten Ein-/Ausgangslatenz. Audiotreiber und Hardwarepuffer kommen hinzu.

Bei Knacksern oder Aussetzern zuerst eine grössere Blockgrösse wählen:

```python
LiveInput(process, blocksize=512)
```

Falls nötig kann zusätzlich eine robustere Gerätelatenz verlangt werden:

```python
LiveInput(process, blocksize=512, latency="high")
```

Der zuletzt gemeldete Unter- oder Überlauf steht in `player.last_status`; die ungefähre Callback-Auslastung in `player.cpu_load`.

## Regeln für `process()`

Die Funktion läuft im Audiothread und muss vor dem nächsten Block fertig sein.

- Keine Dateien öffnen, lesen oder schreiben.
- Kein `print()` pro Audioblock.
- Keine Fenster oder Plots aus `process()` heraus öffnen.
- Keine langen Python-Schleifen; möglichst NumPy-Operationen verwenden.
- Zustände wie Filterverzögerungen ausserhalb der Funktion anlegen und zwischen den Blöcken erhalten.
- Immer ein Array mit derselben Form wie der Eingangsblock zurückgeben.

Ein Fehler in `process()` stoppt den Stream und wird über `player.check()` wieder im Hauptprogramm ausgelöst. `show_controls(..., check=player.check)` prüft dies automatisch.

## Offline und realtime mit derselben Funktion

Eine zustandslose Funktion kann unverändert offline verwendet werden:

```python
import soundfile as sf
import sounddevice as sd

x, fs = sf.read("audio/drums.wav", dtype="float32", always_2d=True)

y = process(x)

sf.write("output/drums-processed.wav", y, fs)

sd.play(y, fs)
sd.wait()
```

Abspielen mit `sd.play(...)` oder abspeichern mit `sf.write(...)` bleiben also weiterhin möglich. Realtime ergänzt dies dort, wo unmittelbares Hören beim Experimentieren hilfreich ist.

Bei zustandsbehafteten Algorithmen muss definiert sein, wann ihr Zustand zurückgesetzt wird. Das ist sowohl offline als auch realtime dieselbe DSP-Frage.

## Pedalboard später ergänzen

Pedalboard kann später innerhalb von `process()` verwendet werden. Die Array-Achsen sind dabei zu beachten: `dspplay` und `sounddevice` verwenden `(frames, channels)`, Pedalboard üblicherweise `(channels, frames)`.

Konzeptionell:

```python
def process(block):
    plugin_input = block.T
    plugin_output = plugin(plugin_input, fs, reset=False)
    return plugin_output.T
```

`reset=False` erhält den Pluginzustand zwischen aufeinanderfolgenden Blöcken. Damit kann die Realtime-Hülle später dieselbe bleiben, während Pedalboard-Effekte, VST3- oder Audio-Unit-Plugins als zusätzliche Prozessoren dazukommen.

## Enthaltene Beispiele

- `examples/gain_file.py`: Gain auf einem WAV-Loop
- `examples/saturation_file.py`: zwei Regler und logarithmische Skalierung
- `examples/gain_live.py`: Live-Eingang zu Ausgang

Die Beispiele werden aus dem Projektordner gestartet:

```bash
uv run python examples/gain_file.py
```

## Noch bewusst offen

Dieser erste Entwurf enthält noch keine automatische Parameterglättung, keinen Bypass, keine Pegelanzeige, keine Aufzeichnung und keinen sicheren Adapter für beliebige Pedalboard-Plugins. Diese Punkte sollten erst ergänzt werden, nachdem die Grundform `block -> process(block) -> output` im Kurs praktisch erprobt wurde.

## Technische Grundlage

- [sounddevice: Streams using NumPy Arrays](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html)
- [SoundFile documentation](https://python-soundfile.readthedocs.io/en/latest/)
- [Pedalboard API](https://spotify.github.io/pedalboard/reference/pedalboard.html)

