# AnycubicNFCTaggerQT5
NFC-Chip tagger for Filament-Roles. Read existing tags, write new tags. #anycubic #filament #nfc


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