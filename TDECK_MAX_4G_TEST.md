# T-Deck MAX 4G (A7682E) – overblik og testvejledning

Branch `tdeck-max-cellular`, bygget oven på beta_106. Gør T-Deck MAX's indbyggede
SIMCom A7682E 4G-modem brugbart: opkald, SMS og mobildata. Kun
`LilyGo_TDeck_Max_companion_radio_touch` får 4G (`HAS_CELLULAR=1`); de øvrige
boards bygger uændret.

Verificeret på en T-Deck MAX med Telenor-SIM: modem op, SIM og netværk fundet,
udgående og indgående opkald med lyd begge veje, data-forbindelse med IP.

## Hvad er lavet

**Firmware (altid tilgængeligt, uden app):**

| Del | Fil |
|---|---|
| Modem-tjeneste: egen FreeRTOS-task, AT-motor, SIM/PIN, netværk, opkald, SMS (UCS2, æøå/emoji), HTTP(S) via modemets egen stack | `variants/lilygo_tdeck_max/CellularService.{h,cpp}` |
| Modem-strøm, PWRKEY og højttaler-mux via XL9555 | `variants/lilygo_tdeck_max/TDeckMaxBoard.{h,cpp}` |
| 4G-ikon i statuslinjen ("4G"/"R"/"4G!" + 0–4 streger) | `src/ui-touch/UITask.cpp` |
| Opkaldsvindue (Svar/Afvis/Læg på) over alt andet, vækker skærmen, ringer | `src/ui-touch/UITask.cpp`, `src/ui-touch/CellUi.cpp` |
| SMS-indbakke på SD-kortet (`meshcomod/sms_inbox.txt`, nyeste 50) | `src/ui-touch/CellUi.cpp` |
| Kortfliser over 4G når Wi-Fi er nede og Data er slået til | `src/ui-touch/UITask.cpp` |
| Lua-API `wada.cell` + `app.on_cell`, ny app-tilladelse "4G: calls, SMS and mobile data" | `src/ui-touch/LuaAppHost.{h,cpp}`, `UITask.cpp` |
| USB Files må skrive `.lang`-filer i `meshcomod/lang/`; `apps/` og `lang/` oprettes ved opstart | `src/helpers/esp32/UsbFilesProtocol.h`, `CellUi.cpp` |
| App-ikonnavnet `phone` (telefonrør) til Lua-apps | `src/ui-touch/UITask.cpp` |
| E-paper: tekstmarkøren blinker ikke (hvert blink var en skærmopdatering, og hver 10. blev en fuld) | `src/ui-touch/UITask.cpp` |

**Telefon-appen** (`deploy/apps/phone/1.0/`): statuskort, taltastatur (også fra
det fysiske tastatur), seneste opkald, SMS-indbakke med svar, modemside og
opkaldsskærm. Host-test: `scripts/lua-harness/phone/test.lua`.

**Dansk sprogfil** (`deploy/apps/lang/da.lang`): hele brugerfladen fra beta_106
plus 4G-teksterne.

**Værktøj:** `scripts/usbfiles_push.py` lægger filer på enheden over USB Files
(samme protokol som files.wadamesh.com).

Pins følger LilyGos T-Deck MAX-eksempler: ESP32 RX = GPIO 11, TX = GPIO 10,
RI = GPIO 7, DTR = GPIO 8; modem-forsyning = XL9555 linje 0, PWRKEY = linje 8,
højttaler-mux = linje 10.

## Byg og flash

```bash
~/.platformio/penv/bin/pio run -e LilyGo_TDeck_Max_companion_radio_touch -t upload
```

Gennem en USB-dock kan esptool fejle, når den skifter til 921600 baud. Brug så
460800 direkte med esptool, eller sæt enheden direkte i computeren. Luk
Wadamesh-faner i Chrome, som bruger Web Serial, før du flasher.

## Læg app og sprog på kortet

Åbn **Apps → USB Files** på enheden, og kør:

```bash
python3 scripts/usbfiles_push.py auto \
  deploy/apps/phone/1.0/phone.lua:/sd/meshcomod/apps/phone.lua \
  deploy/apps/phone/1.0/phone.json:/sd/meshcomod/apps/phone.json \
  deploy/apps/lang/da.lang:/sd/meshcomod/lang/da.lang
```

Vælg derefter **Dansk** under sprog i Store.

## Testtrin

Batteri skal være tilsluttet (modemet trækker mere, end USB alene kan give), og
4G-antennen skal være monteret. Seriel log: `pio device monitor -b 115200`,
linjer med `[CELL]`.

1. **Tænd modem:** Telefon → modemsiden → *Tænd*. Første gang: *Allow*, og tryk
   igen. Forventet: `modem ready`, `sim ready`, `reg=home op=<operatør>`, og
   "4G" med streger i statuslinjen.
2. **Ring ud:** tast et nummer, *Ring op*. Lyd begge veje, *Læg på*.
3. **Ring ind:** med en anden app åben skal firmwarens opkaldsvindue komme frem
   og ringe; *Svar*, *Læg på*.
4. **SMS:** send en SMS med æøå til SIM-kortet; den skal stå i indbakken, også
   hvis Telefon-appen var lukket. Svar fra indbakken.
5. **Data:** *APN* (fx `internet`), *Data til*, *Test net* → "HTTP 200".
6. **Kort over 4G:** slå Wi-Fi fra, Data til, åbn kortet et nyt sted. Fliserne
   kommer (langsommere end over Wi-Fi) og gemmes.

## Kendte begrænsninger

- Ingen fuld IP-forbindelse for hele enheden: PPP er ikke slået til i den
  ESP32 Arduino-core, beta_106 bygger med. Kortfliser og `wada.cell` går gennem
  modemets egen HTTP-stack; `wada.net` og resten bruger stadig kun Wi-Fi.
- SMS over 70 tegn (sammensatte SMS) er ikke understøttet.
- SMS der kom, mens modemet var slukket, hentes ikke ved opstart.
- Ingen modemindstillinger i firmwarens egne Indstillinger; de ligger i
  Telefon-appen.
