# fontmerge

Automatically merge fonts used in a Matroska file.

## Dependences :

Use the package manager [pip](https://pip.pypa.io/en/stable/).

```bash
pip install argparse ass fontTools matplotlib colorama
```

## Usage

```text
usage: fontmerge.py [-h] [--mkvmerge path] [--fontfolder path] subtitles mkv

Automatically merge fonts used in a Matroska file.

positional arguments:
  subtitles          Subtitles containing fonts to be merged. Must be an ASS file.
  mkv                Video where the fonts will go. Must be a Matroska file.

optional arguments:
  -h, --help         show this help message and exit
  --mkvmerge path    Path to mkvmerge.exe if not in variable environments.
  --fontfolder path  Add a file with fonts to use.
```
