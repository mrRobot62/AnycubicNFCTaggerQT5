# AnycubicNFCTaggerQT5
NFC-Chip tagger for Filament-Roles. Read existing tags, write new tags. #anycubic #filament #nfc

- **NOTE** : Version 0.1 is not abel to write NFC-Tags - it's under construction

## No Reader found 
- initial screen
<img width="624" height="453" alt="image" src="https://github.com/user-attachments/assets/69862b39-8710-4ed2-80ac-509286d2cd52" />

## Reader found, no NFC Tag available
- Filament and color choosed
<img width="624" height="453" alt="image" src="https://github.com/user-attachments/assets/b64727a8-d6c8-4e0b-96f3-b223642d81fc" />

## NFC-Tag read
- NFC Tag read and interpreted chip data as log displayed
- Filament & color automatically selected
<img width="714" height="607" alt="image" src="https://github.com/user-attachments/assets/803ec423-9dde-4bc5-9c21-dbc784b99882" />

## Learning Anycubic color shades
- Read a "new" Anycubic filament color and update internal filament/color configuration
  <img width="631" height="640" alt="image" src="https://github.com/user-attachments/assets/da504bb1-3018-4c2a-8e9b-6d9219aa4adf" />

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
