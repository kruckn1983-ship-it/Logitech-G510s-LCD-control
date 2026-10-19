# Eigene Bildschirme – Kurzanleitung

Über die linke Navigation öffnest du **LCD-Bildschirme** und wählst Screens im **Dropdown** aus. Du kannst System, Media Center, Spiele und Netzwerk gestalten und mit **Neuer Screen…** weitere benannte Bildschirme anlegen, ohne feste Anzahl. Eigene Screens lassen sich umbenennen und nach Bestätigung löschen; die fünf eingebauten Screens bleiben erhalten. Bildschirmnamen und physische Tasten sind voneinander getrennt.

Die Vorschau liegt mittig, Werkzeuge und Elemente rechts. Beim Vergrößern des
Fensters wächst die Vorschau proportional; Ziehen und Skalieren bleiben auf die
160 × 43 LCD-Pixel bezogen. Kleine Fenster können bei Bedarf gescrollt werden.
Maximieren nutzt die verfügbare Arbeitsfläche. **F11** oder **Vollbild** blendet
auch den Fensterrahmen aus; mit **Esc** kehrst du zur vorherigen Fensteransicht
zurück. Speichern und Status bleiben unten erreichbar.

## LCD-Tasten

**L1** blättert durch **System → Media Center → Spiele → Netzwerk → Uhr**, danach durch alle eigenen Screens in Anlegereihenfolge und zurück zu System.
**L2–L5** sind Funktionstasten des aktiven Bildschirms. Unter **LCD-Tasten**
wählst du einen Bildschirm und für jede Taste eine Aktion; Änderungen werden
sofort gespeichert und beim nächsten Tastendruck gelesen.

Im Media Center gilt zunächst: **L2 vorheriger Titel, L3 nächster Titel,
L4 Play, L5 Pause**. Im Uhr-Screen: **L2 Uhr-Layout zurück, L3 Uhr-Layout weiter**;
L4/L5 bleiben unbelegt. Auf den anderen Bildschirmen sind die Tasten zunächst
unbelegt. Bereits ausdrücklich gespeicherte Belegungen werden nicht überschrieben;
die Uhr-Aktionen lassen sich unter **LCD-Tasten → Uhr** zuweisen. Zusätzlich stehen Play/Pause-Umschaltung, Lautstärke −/+ (5 Prozentpunkte),
Stummschaltung und direkte Bildschirmwechsel zur Auswahl. Medienaktionen gehen
an einen einzelnen MPRIS-Player (aktive Wiedergabe vor Pause, bei Gleichstand
Browser-Integration bevorzugt), niemals an alle Player gleichzeitig. Webradio
ohne MPRIS kann angezeigt, damit aber nicht gesteuert werden. Aktionsfehler
stehen im Journal von `g510-lcd-buttons.service`.

Die automatische Medien-/Spieleumschaltung bleibt erhalten. Eine manuelle Wahl
per L1 oder über **Bildschirm jetzt auf dem LCD anzeigen** hat Vorrang während
der laufenden Wiedergabe; nach mindestens fünf Sekunden ohne Wiedergabe wird
dieser Vorrang aufgehoben. Das gilt auch, wenn L1 gerade den automatisch
angezeigten Screen auswählt. Die Bildschirmwahl und die L1-Taste in der
Editor-Vorschau wechseln auch das echte LCD; die vier unteren Schaltflächen
zeigen die Belegung, führen aber
keine Aktionen aus.

Die Belegung liegt in `~/.local/share/g510-lcd/lcd_keys.json`. Die bisherigen
Layout-Schlüssel `L2` bis `L5` bleiben aus Kompatibilitätsgründen unverändert:
Sie bezeichnen intern System, Media Center, Spiele und Netzwerk, nicht mehr
die direkten Bildschirmtasten. Bestehende Layouts werden nicht migriert oder
überschrieben.

Eigene Namen, Reihenfolge und fortlaufende IDs liegen in
`~/.local/share/g510-lcd/screens.json`, ihre Layouts in `custom_screens.txt`
als `SCREEN L6`, `SCREEN L7` usw. Neue Screens beginnen leer und mit
unbelegten Funktionstasten. Unter **LCD-Tasten** stehen sie sofort als
Bildschirm und als Ziel einer Wechselaktion zur Verfügung. Beim Löschen
werden Verweise auf diesen Screen unbelegt; seine ID wird nicht erneut vergeben.
Wird der gerade angezeigte Screen gelöscht, wechselt das LCD zu System.
Die Anzahl der Screens hat keine feste Programmgrenze; die bestehenden
Elementgrenzen je Layout und die Größe des LCD bleiben unverändert.

Tests für Tastenaktionen, Entprellung und manuelle Bildschirmpriorität:
`QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`

## Grundlagen

1. **Bildschirm auswählen** – Wähle oben im Dropdown System, Media Center, Spiele, Netzwerk, Uhr oder einen eigenen Screen. Die Auswahl gilt sofort für Vorschau und LCD. „Alle Einstellungen jetzt speichern“ übernimmt im Reiter LCD-Bildschirme bzw. LCD-Tasten zusätzlich den dort ausgewählten Bildschirm und prüft die zurückgelesene Bildschirmwahl. Fehler beim Übernehmen werden ausdrücklich gemeldet; die Bestätigung ist kein Nachweis der physischen LCD-Ausgabe.
   - **Uhr bietet 20 fertige Designs.** Unter **Uhr-Design** direkt auswählen oder mit **Zurück / Weiter** blättern. Die einzelnen Bestandteile sind nicht frei verschiebbar; Hinzufügen und Importieren bleiben deaktiviert. Die erste Variante **Digital pur** ist die bisherige minimalistische Digitaluhr.
   - **Alle anderen Bildschirme kannst du frei gestalten.** Media Center und Spiele haben bei leerem Layout eine automatische Ansicht; eigene Screens starten leer.

2. **Sensor hinzufügen** – Wähle im ersten Auswahlfeld einen Sensor (zum Beispiel CPU-Auslastung, RAM oder GPU-Temperatur). Wähle **Zahl** für eine reine Zahlenanzeige, **Balken** für einen Balken mit danebenstehendem Zahlenwert oder **Füllbalken mit Wert** für den Zahlenwert direkt im Balken. Für normale Balken kannst du außerdem eine waagerechte oder senkrechte Ausrichtung einstellen. Klicke anschließend auf **Hinzufügen**. Senkrechte Balken zeigen standardmäßig ein kurzes Label über dem Balken; für die 20 CPU-Threads gibt es kompakte Labels C1 bis C20. Ein leeres Beschriftungsfeld blendet das Label aus.

3. **Text hinzufügen** – Klicke auf **Add Text...**, gib den gewünschten festen Text ein (zum Beispiel eine Beschriftung oder einen Namen) und füge ihn wie jedes andere Element zur Vorschau hinzu. Leerzeichen und Unterstriche bleiben beim Speichern erhalten. Pro Bildschirm sind bis zu vier Textfelder möglich.

4. **Element verschieben** – Ziehe es mit der Maus an die gewünschte Stelle in der Vorschau. Dort wird es auch auf dem Tastaturdisplay erscheinen.

5. **Bild hinzufügen** – Klicke auf **Import Image...** und wähle ein Bild auf deinem Rechner aus. Es wird automatisch verkleinert und für das kleine Schwarz-Weiß-Display umgewandelt. Anschließend kannst du es wie jedes andere Element verschieben.

6. **Balken oder Bild skalieren** – Bewege den Mauszeiger nahe an das rechte Ende eines Balkens oder an die rechte untere Ecke eines Bildes. Ein kleines blaues Quadrat erscheint. Ziehe es, um die Größe anzupassen.

7. **Zahlen oder Text skalieren** – Diese Elemente bestehen aus Text; die kleinen eingebauten Display-Schriften lassen sich nicht stufenlos vergrößern. Deshalb gibt es dafür keinen Ziehpunkt. Wähle vor dem Hinzufügen im Auswahlfeld **Text Size** eine Größe (Small/Medium/Large/Huge). Bei bereits vorhandenen Elementen kannst du über die Schaltfläche neben dem jeweiligen Eintrag rechts durch die Größen wechseln. Sensor-Labels und ihre Werte verwenden dieselbe Größe.

8. **Element entfernen** – Klicke rechts in der Liste neben dem Element auf **✕**.
9. **Anzeigenamen ändern** – Bearbeite in **Elements on this screen** (Elemente auf diesem Bildschirm) das Textfeld neben einem Sensor- oder Textelement und drücke Enter. Der Name wird mit dem Bildschirm gespeichert und erscheint in der Vorschau und auf der Tastatur. Temperatursensoren haben kompakte Standardnamen wie **CPU** und **GPU** (z. B. `CPU 32°C`, `GPU 45°C`); das Gradzeichen wird als kleiner Kreis gezeichnet. Die Namen lassen sich einzeln ändern.

10. **Datums- und Zeitformat wählen** – Bei **Date** und **Time** wählst du das Format über die kompakte Auswahl in der Zeile. Sie ersetzt das Label-Feld, da Datum und Uhrzeit ohne Label angezeigt werden. Es werden nur unterstützte Formate angeboten; die Wahl wird pro Bildschirm gespeichert und die Vorschau aktualisiert sich sofort.

11. **Mit einer Dashboard-Vorlage starten** – Wähle **CPU / GPU performance**, **Temperature overview** oder **System overview** und klicke auf **Apply layout preset...**. Der gewählte bearbeitbare Bildschirm wird nach Bestätigung ersetzt; die erzeugten Elemente kannst du danach wie gewohnt verschieben, umbenennen oder entfernen.

Das war's. Eine **Speichern**-Schaltfläche gibt es nicht: Jede Änderung (Verschieben, Skalieren, Hinzufügen oder Entfernen) wird sofort gespeichert.

## Wissenswertes

- **Das Display ist klein:** 160 × 43 Pixel, genau wie das echte LCD. Bei zu vielen Elementen können sich Zeilen überlappen oder am unteren Rand abgeschnitten werden. Die Vorschau entspricht der echten Anzeige. Wenn etwas in der Anwendung falsch aussieht, sieht es auch auf der Tastatur falsch aus – lass genügend Abstand.
- **L4 während eines Spiels:** Die automatische Spielübersicht ersetzt auf der Tastatur vorübergehend das gespeicherte L4-Layout. Wenn ein Spiel läuft, zeigt der Editor ebenfalls diese Übersicht; du kannst Logo sowie CPU- und GPU-Anzeigen direkt auf der Vorschau ziehen. Die Positionen werden sofort gespeichert und gelten auch für die Anzeige auf der Tastatur. Wenn kein Spiel läuft, kannst du wie gewohnt das gespeicherte L4-Layout bearbeiten.
- **Spiel-Logo:** Das Dashboard nutzt das ganze Display (160 × 43 Pixel); CPU und GPU werden im Gaming-Screen nicht mehr angezeigt. Der Dienst sucht das echte Steam-Logo des laufenden Spiels (alte und Hash-Cache-Ordner, alle üblichen Steam-Verzeichnisse, auch Flatpak) und wandelt es mit `src/png-to-lcd.py --best-logo` automatisch in ein Schwarz-Weiß-Logo um (adaptive Schwelle, Alphamaske für helle Schriftzüge, Plaketten wie bei BioShock als dunkle Fläche mit heller Schrift). Nur wenn kein Artwork gefunden wird, rendert `src/title-to-lcd.py` den Spielnamen aus dem Steam-Manifest als fettes Schrift-Logo. Die Ergebnisse liegen unter `~/.local/share/g510-lcd/game_logos/<appid>.bin/.size`. Mit `python3 scripts/pregenerate-game-logos.py` lassen sich alle Logos der installierten Steam-Spiele im Voraus erzeugen (`--force` erzeugt neu). Zum Ersetzen eines Logos die passende `.bin`/`.size` löschen.
- **Eigene Spiel-Logos:** Am einfachsten im Tab **Game Logos** der App: Spiel suchen/auswählen (Vorschau auf 160 × 43), „Choose own logo...“ klicken und ein Bild wählen; „Back to automatic logo“ stellt das automatische Logo wieder her. Manuell: Lege ein Bild als `~/.local/share/g510-lcd/custom_logos/<appid>.png` ab (die App-ID steht in der Steam-URL des Spiels bzw. im Dateinamen `appmanifest_<appid>.acf`). Es hat Vorrang vor allem anderen (auch vor `assets/logos/<appid>.png` im Projekt). Weiße Schrift auf dunklem Grund wird automatisch invertiert, das Logo wird zugeschnitten, so groß wie möglich skaliert und zentriert. Am besten ein sauberes, kontrastreiches Bild ohne Verlauf. Einfacher geht es mit `python3 scripts/add-game-logo.py <appid> <bild.png>`; ohne Bild entfernt `python3 scripts/add-game-logo.py <appid> --remove` das eigene Logo wieder.
- **Für jeden Elementtyp gilt ein eigenes Limit pro Bildschirm:** 32 Sensoren, 2 Bilder, 4 Textfelder, 8 Rahmen und ein Audio-Visualizer. Das sind keine gemeinsamen Gesamtlimits. Die Anwendung meldet, wenn eines der Limits erreicht ist.
- **Rahmen** gliedern ein Layout ohne Hintergrundfüllung. Über **Rahmen hinzufügen** anlegen, am Rand verschieben oder an der rechten unteren Ecke skalieren. Der Innenbereich bleibt für die enthaltenen Sensoren anklickbar; ein Rahmen ist keine Gruppe und verschiebt die Sensoren nicht mit.
- **Nicht jeder Sensor kann als Balken angezeigt werden.** Balken gibt es nur für Werte mit einem sinnvollen Bereich von 0 bis 100 Prozent oder einem geeigneten Temperaturbereich. Bei ungeeigneten Sensoren informiert dich die Anwendung und zeigt den Wert stattdessen als Zahl an.
- **Senkrechte Balken** eignen sich für kompakte Anzeigen mehrerer CPU-Kerne oder der GPU. Bewege den Mauszeiger nahe an das untere Ende und ziehe den Griff nach oben oder unten, um die Höhe anzupassen.
- **Der blaue Ziehpunkt erscheint nur bei Bedarf.** Er wird nur sichtbar, wenn sich der Mauszeiger nahe an einem Balken oder an einem skalierbaren Bild befindet. Früher waren alle Ziehpunkte gleichzeitig sichtbar, was unübersichtlich war.
- **Die Sensorauswahl erklärt die Werte.** Die Beschreibung unter dem Auswahlfeld wird beim Wechsel der Auswahl aktualisiert. So musst du nicht raten, was zum Beispiel „GPU Hotspot Temp“ oder „Max Temp Seen“ bedeutet.

## Auf der echten Tastatur anzeigen

Drücke L1 wiederholt bis zum gewünschten Bildschirm, oder wähle ihn im Reiter
**LCD-Tasten** und klicke **Bildschirm jetzt auf dem LCD anzeigen**.
Die Layoutänderungen werden weiterhin automatisch gespeichert.

## Dashboard-Vorlagen

Wähle eine Vorlage und klicke auf **Apply layout preset...**, um den ausgewählten bearbeitbaren Bildschirm zu ersetzen. Vorher fragt die Anwendung nach einer Bestätigung.

- **CPU / GPU performance** – acht Balken für einzelne logische CPU-Kerne, GPU-Temperatur und -Auslastung, RAM und Netzwerk-Up-/Downloadraten.
- **Temperature overview** – CPU-Temperatur, GPU-Edge-/Hotspot-/VRAM-Temperatur und die maximale CPU-Temperatur seit Dienststart.
- **Network, disks & clock** – Down-/Upload, Festplattenbelegung als Balken, Uhrzeit und Datum.
- **Media player (Medienplayer)** – Titel, Interpret, Laufzeit und Audio-Visualizer. Die Laufzeit im Stil **Bar** zeigt die aktuelle Zeit links und die Gesamtdauer rechts neben dem Fortschrittsbalken; bei Livestreams ohne verlässliche Gesamtdauer gibt es keinen Fortschrittsbalken.
- **Systemübersicht** – eingerahmtes Kompaktlayout: links CPU-Temperatur und 20 einzelne Thread-Balken; mittig GPU-Temperatur und drei Balken; rechts RAM-Belegung mit integriertem Prozentwert, Uhrzeit mit Sekunden und Upload/Download.

Die Höhe der CPU-Balken zeigt die **Auslastung**, nicht die Temperatur. Linux stellt die Temperatur einzelner CPU-Kerne nicht auf jeder Hardware bereit.

### System-Screen mit 20 Threads

Das Layout ist auf den Intel Core i9-10850K (10 physische Kerne, 20 logische
Threads) und die NVIDIA RTX 3080 abgestimmt. Die CPU-Balken stehen von links
nach rechts für Linux `cpu0` bis `cpu19`; beide SMT-Threads eines Kerns sind
eigene Balken, keine zusammengefassten oder kopierten Werte. Der LCD-Dienst
misst alle Thread-Zähler gemeinsam ungefähr einmal pro Sekunde und hält die
Werte bis zur nächsten Messung stabil. Die einmalige Editor-Vorschau verwendet
ein eigenes kurzes Messintervall. Fehlende Messgrundlagen werden nicht als
erfundene CPU-Aktivität dargestellt.

Die drei GPU-Balken zeigen von links nach rechts **GPU-Auslastung**,
**VRAM-Belegung** und **GPU-Temperatur**. Die ersten beiden skalieren von
0 bis 100 Prozent; der Temperaturbalken verwendet wie andere Temperaturbalken
0 bis 90 Grad Celsius. Darüber steht die Temperatur zusätzlich als Zahl.
Eine GPU-Kerntemperatur ist kein Maß für die Anzahl der GPU-Kerne.

Rechts steht **MEM** für die RAM-Belegung, **UP** für Upload und **DN** für
Download der aktiven Schnittstelle. Die kompakte Ratendarstellung wechselt
zwischen B/s, KiB/s, MiB/s und GiB/s (bei Bedarf TiB/s); die Einheiten bleiben
auch bei hohen Raten sichtbar. Es handelt sich weiterhin um Datenverkehr,
nicht um die gebuchte Anschlussgeschwindigkeit.

Alle Sensoren, Beschriftungen und Rahmen bleiben bearbeitbar. Der System-Screen
und die Vorlage **Systemübersicht** verwenden dasselbe Layout. Andere vorhandene
Screen-Layouts werden durch die Auswahl dieser Vorlage nicht verändert.

## 20 Uhr-Designs

Wähle den Screen **Uhr** und blättere auf der Tastatur mit **L2 zurück** bzw.
**L3 weiter** (Standardbelegung). Nach Nummer 20 folgt wieder Nummer 1;
rückwärts geht es von Nummer 1 zu Nummer 20. **L1** wechselt weiterhin den
Screen und nicht das Uhr-Design. Die Uhr-Aktionen gelten nur im aktiven
Uhr-Screen, führen keine Medienaktionen aus und sind unter **LCD-Tasten**
änderbar. Die vier unteren Schaltflächen der Editor-Vorschau zeigen weiterhin
nur die Tastenbelegung an; zum Blättern im Tool dienen die eigenen
**Zurück / Weiter**-Schaltflächen neben **Uhr-Design**.

| Nr. | Design | Anzeige |
| --- | --- | --- |
| 01 | Digital pur | Große Stunden/Minuten, kleinere Sekunden und Datumszeile |
| 02 | Panorama | Uhrzeit mit Sekunden in einer breiten Zeile |
| 03 | Dashboard | Eingerahmte Digitalzeit und separate Sekundenbox |
| 04 | Zeitkacheln | Drei Karten für Stunden, Minuten und Sekunden |
| 05 | Siebensegment | Markante Segmentziffern und kleinere Sekunden |
| 06 | Kontur | Große Umrissziffern statt ausgefüllter Ziffern |
| 07 | Nachtmodus | Helle Ziffern auf dunklem Zeitfeld |
| 08 | Analog links | Zifferblatt links, Digitalzeit und Datum rechts |
| 09 | Analog rechts | Gespiegelte Analog-/Digital-Aufteilung |
| 10 | Zifferblatt | Mittiges Zifferblatt mit 12/6, Digitalzeit und Sekunden daneben |
| 11 | Binäruhr | Sechs BCD-Ziffernspalten für HHMMSS |
| 12 | Zeitspalten | Stunden, Minuten und Sekunden mit feinen Trennlinien |
| 13 | Gestapelt | Stunden über Minuten; Wochentag, Datum und Sekunden rechts |
| 14 | Sekundenlauf | Digitalzeit und Fortschrittsbalken der aktuellen Minute |
| 15 | Kalender | Kalenderkarte mit großem Tag neben der Digitalzeit |
| 16 | Klappzahlen | Stunden-/Minutenkarten im Klappzahlen-Stil, keine mechanische Animation |
| 17 | Punktmatrix | Uhrzeit mit Sekunden aus einzelnen Pixelpunkten |
| 18 | Rahmenlos | Luftige Anordnung mit Wochentag über der Digitalzeit |
| 19 | Terminal | Kompakte Zeit und Datum im Terminal-Stil |
| 20 | Tagesfortschritt | Digitalzeit, Datum und Position im laufenden Tag |

Die Binäruhr zeigt pro Dezimalziffer von oben nach unten die Bitwerte
**8, 4, 2, 1**; gefüllte Felder werden addiert. Der Sekundenlauf ist bei
Sekunde 0 leer und bei 59 voll. Die Tagesleiste zeigt die lokale Uhrzeit
zwischen 00:00 und 23:59:59, keine Messung der tatsächlichen Tagesdauer an
Sommerzeit-Umstellungstagen.

Die Auswahl liegt als Zahl **0 bis 19** in
`~/.local/share/g510-lcd/clock_layout` und wird atomar gespeichert. Ohne Datei
gilt **Digital pur**. Ein fehlerhafter Wert wird ausdrücklich gemeldet und
nicht still durch ein anderes Layout ersetzt. Im Tool lässt sich über die
direkte Auswahl wieder ein gültiges Design speichern.

Der LCD-Dienst und die Vorschau lesen dieselbe Auswahl; ein Tastendruck wird
beim nächsten Aktualisieren sichtbar, ohne Dienstneustart. Das Tool übernimmt
physische Layoutwechsel auch in sein Dropdown, ohne die Auswahl zurückzuschreiben.
Die Uhr verwendet die lokale Systemzeit einschließlich Zeitzone und Sommerzeit,
deutsche Wochentage sowie das vollständige Datum; die kompakten Analogvarianten
zeigen nur das numerische Datum. Zusätzliche Schriftdateien oder Sprachpakete
sind nicht erforderlich. Alle anderen Screen-Layouts bleiben unverändert.

## Standardbelegung und Profile

- **Standardlayouts wiederherstellen:** Setzt die vier bearbeitbaren Layouts auf die angebotenen Vorlagen zurück, nach Bestätigung und Sicherung als `custom_screens.txt.vor-standardbelegung`. Die Funktionstastenbelegung bleibt unverändert.
- **Profile (Spiel, Arbeit, Nacht):** Wähle ein Profil und klicke auf **Profil anwenden**. Die LED-Farbe wird gesetzt (und bleibt auch nach dem Neustart) und der LCD-Bildschirm wechselt: Spiel → L2 (rot), Arbeit → L4 (blau), Nacht → Uhr (dunkelrot).

**Medien ohne MPRIS:** Player wie radiotray-ng (Webradio) melden sich nicht per MPRIS. Für sie liest die Anwendung den Stream-Titel aus PulseAudio/PipeWire; ein Titel der Form „Interpret - Titel“ wird in Interpret und Titel aufgeteilt. Laufzeit (Elapsed) gibt es dort nicht.

**Automatische Medienerkennung:** Anmeldeklänge (`desktop-*`) und als Ereignis,
Benachrichtigung oder Animation gekennzeichnete Audiostreams lösen L3 nicht aus.
Pausierte MPRIS-Player behalten ihre Titelanzeige, aktivieren L3 aber nicht;
gestoppte Player werden ignoriert. Aktives Webradio ersetzt einen pausierten
Player ohne dessen alte Laufzeit zu übernehmen. Titel und Laufzeit stammen vom
gleichen Player; Browser-Integration und Browser dürfen ihre Metadaten nur bei
übereinstimmender Medien-URL oder übereinstimmendem Titel kombinieren.

Regressionstests (benötigen die Build-Abhängigkeiten des Dienstes, aber keine
Tastatur): `python3 -m unittest discover -s tests -p test_media.py -v`

### Netzwerkverbindung & Datenraten

Die Netzwerkvorlage zeigt vier klar getrennte Zeilen: **LINK** mit der aktiven
Schnittstelle, **DL** (Download), **UL** (Upload) und **IP** (lokale IPv4-Adresse).
Rechts neben DL und UL liegen zwei getrennte Verlaufsgrafiken. Zwischen den
Zahlen und den Diagrammen bleiben mindestens acht LCD-Pixel frei; lange
Zahlen werden bei Bedarf kleiner dargestellt. Auch zur IP-Zeile bleibt Abstand.

Die Verläufe enthalten die letzten **60 Messwerte**, von links (alt) nach
rechts (neu), auf dem Netzwerk-Screen ungefähr eine Minute. Beide haben eine
eigene automatische Höhenskala; die Höhe ist deshalb kein direkter Vergleich
zwischen Download und Upload. Ohne Verkehr ist die Kurve flach. Fehlende Daten
zeichnen keine erfundene Aktivität. Bei Verbindungsabbruch, Schnittstellenwechsel,
Zählerrücksetzung oder Dienstneustart beginnt der Verlauf neu.

Die Auswahl bevorzugt die aktive IPv4-Standardroute mit der niedrigsten Metrik,
sonst eine aktive Schnittstelle außer Loopback. Das ist ein Link-Status, kein
Nachweis einer Internetverbindung. Die IP ist nicht die öffentliche Adresse.

Raten stehen in **KiB/s** bzw. **MiB/s** und umfassen den Verkehr der gewählten
Schnittstelle, einschließlich lokaler Übertragungen. Sie sind kein Speedtest.
Ohne Messbasis bzw. bei Zählerrücksetzung oder Schnittstellenwechsel erscheint
**N/V**, eine gemessene ruhende Verbindung zeigt **0 KiB/s**. Ohne aktive
Schnittstelle steht **KEINE VERBINDUNG**; ohne IPv4-Adresse steht **N/V**.
Die Tool-Vorschau liest die Messwerte und den Verlauf des LCD-Dienstes aus
`$XDG_RUNTIME_DIR/g510lcd_network`. Sie schreibt keine Messwerte zurück und
fügt durch Öffnen oder Aktualisieren keine Verlaufspunkte hinzu. Fehlt ein
aktueller Dienst-Snapshot, misst die Vorschau ihre Zahlen über ein kurzes
eigenes Intervall; ein längerfristiger Verlauf ist dann nicht verfügbar.

Die Vorlage lässt sich wie bisher bearbeiten und auf eigene Screens anwenden.
Für die Sensoren **Netzwerk-Downloadrate** und **Netzwerk-Uploadrate** steht der
Anzeigestil **Verlauf** zur Verfügung. Verlaufselemente können einzeln hinzugefügt,
verschoben, an der Ecke in der Größe verändert und entfernt werden.
Der separate Kühlungsbereich wurde entfernt; installierte Treiber, BIOS-Regelung
und LACT bleiben davon unberührt. Temperatur-Sensoren im LCD-Editor bleiben verfügbar.

- **Laufschrift (L3 Media Center):** Sind Titel oder Interpret breiter als das Display, werden sie nicht mehr abgeschnitten, sondern laufen als Laufschrift durch (kurze Pause am Anfang, dann nach links, dann von vorn).
- **Media Center:** Ohne eigene Elemente erscheint automatisch die Medienansicht mit Titel, Interpret, Fortschritt und Audio-Spektrum. Ohne verfügbaren Medientitel erscheint eine dekorative, bewegte Welle mit Musiknote und „BEREIT FUER MUSIK & FILM“. Das ist keine gemessene Audioaktivität. Ein pausierter Titel bleibt mit Pause-Symbol sichtbar.
- **Spiele:** Ohne erkanntes Spiel und ohne eigene Elemente erscheint eine kleine animierte Raumschiff-Szene mit „Ready to rumble“. Bei erkanntem Spiel übernimmt wieder die Spielansicht. Musik allein aktiviert keine Spielansicht.
- **Eigene Layouts bleiben erhalten:** Die Leerlaufanimationen ersetzen ausschließlich die automatischen Ansichten leerer Media-/Spielelayouts, nicht selbst platzierte Elemente. Animationen laufen auf dem LCD mit dem vorhandenen schnellen Neuzeichnen; die Tool-Vorschau zeigt wie bisher etwa einmal pro Sekunde ein aktuelles Bild.
