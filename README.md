# AnycubicNFCTaggerQT5
NFC-Chip tagger for Filament-Roles. Read existing tags, write new tags. #anycubic #filament #nfc

- **NOTE** : Version 0.1 is not able to write NFC-Tags - it's under construction

## No NFC-Reader found 
- initial screen, reader not connected via USB
<img width="624" height="453" alt="image" src="https://github.com/user-attachments/assets/69862b39-8710-4ed2-80ac-509286d2cd52" />

## NFC-Reader found, no NFC Tag available
- Filament and color choosed
<img width="624" height="453" alt="image" src="https://github.com/user-attachments/assets/b64727a8-d6c8-4e0b-96f3-b223642d81fc" />

## NFC-Tag read
- NFC Tag read and interpreted chip data as log displayed
- Filament & color automatically selected
<img width="714" height="607" alt="image" src="https://github.com/user-attachments/assets/803ec423-9dde-4bc5-9c21-dbc784b99882" />

## Learning Anycubic color shades
- Read a "new" Anycubic filament color and update internal filament/color configuration
  <img width="631" height="640" alt="image" src="https://github.com/user-attachments/assets/da504bb1-3018-4c2a-8e9b-6d9219aa4adf" />

# My subjective researches
Regardless of what you write on the NFC tag, it appears that the ACE Pro only requires the SKU and, if necessary, the color code. Neither temperatures nor other information are transmitted from the ACE Pro to the slicer.

I have also found that only Anycubic SKUs can be used, as the ACE Pro only “understands” these.

## Consequence:
Even if you want to mark your own filaments with an NFC tag, you have to choose an Anycubic SKU.
This information is then also transmitted to the slicer. The slicer then selects an Anycubic filament template.

Therefore, it doesn't matter what temperatures, etc. you write on the NFC tag, as you cannot influence the slicer with it. May usefull to store your individual filament configuration for "this" filament/color for later using

# Further researches on BambuLab machines
It would be interesting to analyze if BambuLab NFC-Tags works in the same manner as Anycubic.
I read that BambuLab use RFID recognition for their filaments/loader. NFC is a sub group of RFID. So maybe it could be possible that.....

If a BambuLab owner is reading this and want to help - below a description how to help

## generating a Byte-Dump from tag
- download this software and install
- do not start the AnycubicNFCTaggerQT5 app, instead use a raw-dump test routine
  -- available inside tests-folder
  -- use an NFC-Reader
  -- change to your installation folder and call `python tests/ntag_dump.py` 
  -- place an NFC-Tag (filament role) on your reader - or move reader around your role
  -- result should be like this
```
00: 1D 72 F5 12   |.r..|
01: 61 0F 10 80   |a...|
02: FE C0 00 00   |....|
03: E1 10 12 00   |....|
04: 7B 00 65 00   |{.e.|
05: 48 41 53 47   |HASG|
06: 46 2D 31 30   |F-10|
07: 36 00 00 00   |6...|
08: 00 00 00 00   |....|
09: 00 00 00 00   |....|
10: 41 43 00 00   |AC..|
11: 00 00 00 00   |....|
12: 00 00 00 00   |....|
13: 00 00 00 00   |....|
14: 00 00 00 00   |....|
15: 41 53 41 00   |ASA.|
16: 00 00 00 00   |....|
17: 00 00 00 00   |....|
18: 00 00 00 00   |....|
19: 00 00 00 00   |....|
20: FF 00 80 00   |....|
21: 00 00 00 00   |....|
22: 00 00 00 00   |....|
23: 00 00 00 00   |....|
24: F0 00 18 01   |....|
25: 00 00 00 00   |....|
26: 00 00 00 00   |....|
27: 00 00 00 00   |....|
28: 00 00 00 00   |....|
29: 5A 00 6E 00   |Z.n.|
30: AF 00 4A 01   |..J.|
31: E8 03 00 00   |....|
32: 00 00 00 00   |....|
33: 00 00 00 00   |....|
34: 00 00 00 00   |....|
35: 00 00 00 00   |....|
36: 00 00 00 00   |....|
37: 00 00 00 00   |....|
38: 00 00 00 00   |....|
39: 00 00 00 4D   |...M|
40: 00 00 00 BD   |....|
41: 00 00 00 FF   |....|
42: 00 00 00 00   |....|
43: 00 00 00 00   |....|
44: 00 00 00 00   |....|
45: 00 00 00 00   |....|
46: READ ERROR
47: READ ERROR
```

# Install
## prepare virutal environment
`python -m venv .venv`

## Windows:
`. .venv/Scripts/activate`

## macOS/Linux:
`source .venv/bin/activate`

## General installation

`pip install -U pip`
`pip install -e .`           


## MacOSX
`brew install pcsc-lite`
`brew services start pcscd`

# Start

`python AnycubicNFCTaggerQT5.py`
AnycubicNFCTaggerQT5


# build a wheel
`pip install build`
`python -m build`
- -> dist/*.whl und dist/*.tar.gz
# EXE 
`pip install "cx-Freeze>=7"`

## Variante A: Modul-CLI
`python -m cx_Freeze build --config pyproject.toml`

## Variante B: direkter Befehl (falls Script installiert)
`cxfreeze build --config pyproject.toml`
