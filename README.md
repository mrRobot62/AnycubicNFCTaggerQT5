# AnycubicNFCTaggerQT5
NFC-Chip tagger for Filament-Roles. Read existing tags, write new tags. #anycubic #filament #nfc

## No Reader found 
<img width="624" height="453" alt="image" src="https://github.com/user-attachments/assets/69862b39-8710-4ed2-80ac-509286d2cd52" />

## Reader found, no NFC Tag available
<img width="624" height="453" alt="image" src="https://github.com/user-attachments/assets/b64727a8-d6c8-4e0b-96f3-b223642d81fc" />

## NFC-Tag read
<img width="714" height="607" alt="image" src="https://github.com/user-attachments/assets/803ec423-9dde-4bc5-9c21-dbc784b99882" />

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
