# dspplay

`dspplay` ist eine kleine Echtzeit-Hülle für den Audio-DSP/Python-Kurs. Die
Studierenden schreiben weiterhin eine gewöhnliche Funktion:

```python
def process(block, fs):
    return 0.5 * block
```

`dspplay` kümmert sich um Audiogerät, Audioblöcke, Datei-Loop, sichere
Wiedergabe und ein minimales Reglerfenster. NumPy und die eigentliche
Signalverarbeitung bleiben sichtbar.

## Installation

Im Entwicklungsordner von `dspplay`:

```bash
uv sync
```

Liegt `dspplay` direkt neben einem bestehenden Kursprojekt, kann es dort als
editierbares Paket hinzugefügt werden:

```bash
uv add --editable ../dspplay
```

Wie die Bibliothek später an die Studierenden verteilt wird, ist noch nicht
festgelegt.

## Ein Signal sicher abspielen

Ein bereits berechnetes Signal wird mit `play_signal(...)` abgespielt:

```python
from dspplay import play_signal

y = 0.5 * x

play_signal(y, fs)
```

Die Funktion wartet bis zum Ende der Wiedergabe. Vorher prüft sie:

- Monoform `(N,)` oder Mehrkanalform `(N, C)`
- nicht leeres Array
- reelle numerische Werte
- keine `NaN`- oder unendlichen Werte
- positive Samplingrate
- Peak innerhalb des erlaubten Bereichs

Ein kritisches Signal wird nicht heimlich normalisiert oder begrenzt. Die
Wiedergabe wird mit einer verständlichen Fehlermeldung verweigert.

## Eine Datei in Echtzeit bearbeiten

Das folgende Beispiel spielt `audio/example_stereo.wav` als Loop. Beim
Verschieben des Reglers verwendet bereits der nächste Audioblock den neuen
Wert:

```python
from dspplay import play_file, slider


gain = slider(
    "Gain",
    value=0.5,
    minimum=0.0,
    maximum=1.0,
)


def process(block, fs):
    return gain.value * block


play_file(
    "audio/example_stereo.wav",
    process,
    controls=[gain],
    title="Gain",
)
```

Die Studierenden müssen dafür weder einen Sounddevice-Callback noch einen
Context Manager schreiben. Die fortgeschrittenen Klassen `FileLoop` und
`LiveInput` bleiben verfügbar, sind aber nicht die normale Kursoberfläche.

## Das Datenmodell

Die öffentliche Schnittstelle folgt derselben Konvention wie das Skript und
das Standardverhalten von SoundFile:

```text
Mono:         (frames,)
Mehrkanal:    (frames, channels)
```

Ein Stereoblock mit 256 Frames hat also `block.shape == (256, 2)`. Ein
Monoblock derselben Länge hat `block.shape == (256,)`.

Sounddevice verwendet intern auch für Mono eine zweidimensionale Form.
`dspplay` wandelt diese Form an der Grenze zur Kursfunktion automatisch um.
`process(...)` muss wieder ein Array derselben Form zurückgeben.

Die Echtzeitdaten verwenden `float32`. Der übliche Wertebereich liegt zwischen
`-1.0` und `+1.0`.

## Die Samplingrate

`process(...)` erhält neben dem Block immer die Samplingrate `fs`:

```python
def process(block, fs):
    return block
```

Bei `play_file(...)` stammt `fs` aus der Audiodatei. Bei `play_input(...)` wird
sie beim Start festgelegt. Filterkoeffizienten, Delayzeiten und LFOs können
damit unabhängig von einer fest eingetragenen Samplingrate berechnet werden.

## Mehrere und logarithmische Regler

Für Frequenzen ist eine logarithmische Reglerskala sinnvoll:

```python
cutoff = slider(
    "Cutoff",
    value=1_000,
    minimum=20,
    maximum=20_000,
    scale="log",
    unit="Hz",
    decimals=0,
)
```

Mehrere Regler werden als Liste an die Wiedergabe übergeben:

```python
play_file(
    "audio/example_stereo.wav",
    process,
    controls=[cutoff, resonance],
    title="Lowpass",
)
```

`slider(...)` begrenzt seinen Wert automatisch auf `minimum` bis `maximum`.
Parametersprünge werden absichtlich nicht geglättet: Ob und wie geglättet
wird, gehört zum DSP-Algorithmus und kann später untersucht werden.

## Live-Eingang

Dieselbe `process(...)`-Idee funktioniert mit Mikrofon, Gitarre oder
Audiointerface:

```python
from dspplay import play_input, slider


gain = slider("Gain", 0.25, 0.0, 1.0)


def process(block, fs):
    return gain.value * block


play_input(
    process,
    controls=[gain],
    samplerate=48_000,
    channels=1,
    title="Live-Gain",
)
```

Beim Live-Betrieb zuerst Kopfhörer und einen niedrigen Ausgangspegel
verwenden. Lautsprecher und Mikrofon können unmittelbar eine Rückkopplung
erzeugen.

## Blockübergreifender Zustand

Während einer Wiedergabe ruft `dspplay` immer denselben Prozessor mit
aufeinanderfolgenden Blöcken auf. Ein ausserhalb von `process(...)` angelegter
Filter-, Delay- oder LFO-Zustand bleibt deshalb zwischen den Aufrufen erhalten.
`dspplay` setzt diesen Zustand nicht an jeder Blockgrenze zurück.

Die konkrete, anfängerfreundliche Schreibweise für solche Zustände wird
zusammen mit den ersten zustandsbehafteten Algorithmen im Kurs festgelegt. Für
die Bibliothek gilt bereits jetzt:

- Blöcke werden der Reihe nach verarbeitet.
- Der Prozessor wird während einer Wiedergabe nicht ersetzt.
- Ein neuer Aufruf von `play_file(...)` oder `play_input(...)` erzeugt einen
  neuen Audiostream.
- Der Zustand gehört dem Prozessor; `dspplay` verändert ihn nicht selbständig.

## Audiogeräte auswählen

Die verfügbaren Geräte lassen sich anzeigen mit:

```python
from dspplay import list_devices

list_devices()
```

Danach kann ein Gerätename oder eine Gerätenummer übergeben werden:

```python
play_file(
    "audio/example_stereo.wav",
    process,
    device="MacBook Pro Speakers",
)
```

Für getrennte Ein- und Ausgänge:

```python
play_input(process, device=(2, 5))
```

## Blockgrösse und Latenz

Der Standardwert ist `blocksize=256`. Bei 48 kHz entspricht ein Block

$$
\frac{256}{48\,000} \approx 5.3\,\text{ms}.
$$

Das ist nur ein Teil der gesamten Ein-/Ausgangslatenz. Audiotreiber und
Hardwarepuffer kommen hinzu.

Bei Knacksern oder Aussetzern zuerst eine grössere Blockgrösse wählen:

```python
play_input(process, blocksize=512)
```

Falls nötig kann zusätzlich eine robustere Gerätelatenz verlangt werden:

```python
play_input(process, blocksize=512, latency="high")
```

## Regeln für `process(...)`

Die Funktion läuft im Audiothread und muss vor dem nächsten Block fertig sein.

- Keine Dateien öffnen, lesen oder schreiben.
- Kein `print()` pro Audioblock.
- Keine Fenster oder Plots aus `process(...)` heraus öffnen.
- Keine langen Python-Schleifen; möglichst NumPy-Operationen verwenden.
- Filter-, Delay- und andere Zustände zwischen den Blöcken erhalten.
- Immer ein Array mit derselben Form wie der Eingangsblock zurückgeben.

Ein Fehler in `process(...)` stoppt den Stream. Auch nicht endliche Werte,
eine falsche Arrayform und ein Peak über `max_peak` werden als Fehler an das
Hauptprogramm zurückgegeben.

## Offline und Echtzeit

Eine zustandslose Funktion kann unverändert auf ein vollständiges Signal oder
auf fortlaufende Blöcke angewandt werden:

```python
import soundfile as sf

from dspplay import play_file, play_signal


def process(block, fs):
    return 0.5 * block


x, fs = sf.read("audio/example_stereo.wav")
y = process(x, fs)

play_signal(y, fs)
play_file("audio/example_stereo.wav", process)
```

Bei zustandsbehafteten Algorithmen muss zusätzlich definiert sein, wann der
Zustand initialisiert oder zurückgesetzt wird. Dieselbe Frage stellt sich auch
bei blockweiser Offline-Verarbeitung.

## Pedalboard später ergänzen

Pedalboard kann später innerhalb von `process(...)` verwendet werden. Die
Arrayachsen sind dabei zu beachten: `dspplay` verwendet für Mehrkanalaudio
`(frames, channels)`, Pedalboard üblicherweise `(channels, frames)`.

Konzeptionell:

```python
def process(block, fs):
    plugin_input = block.T
    plugin_output = plugin(plugin_input, fs, reset=False)
    return plugin_output.T
```

`reset=False` erhält den Pluginzustand zwischen aufeinanderfolgenden Blöcken.
Für Mono benötigt ein späterer Adapter zusätzlich die passende Formumwandlung.

## Enthaltene Beispiele

- `examples/gain_file.py`: Gain auf einem Datei-Loop
- `examples/saturation_file.py`: zwei Regler und logarithmische Skalierung
- `examples/gain_live.py`: Live-Eingang zu Ausgang

Die Beispiele werden aus dem Projektordner gestartet:

```bash
uv run python examples/gain_file.py
```

## Noch bewusst offen

Der zweite Entwurf enthält noch keine automatische Parameterglättung, keinen
Bypass, keine Pegelanzeige, keine Aufzeichnung und keinen sicheren Adapter für
beliebige Pedalboard-Plugins. Ebenfalls offen sind der Verteilungsweg an die
Studierenden und ein gemeinsames Audio-Testfile.

## Technische Grundlage

- [sounddevice: Streams using NumPy Arrays](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html)
- [SoundFile documentation](https://python-soundfile.readthedocs.io/en/latest/)
- [Pedalboard API](https://spotify.github.io/pedalboard/reference/pedalboard.html)
