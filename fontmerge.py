import argparse
import sys
import re
import os
import collections
import ass
import subprocess
import distutils.spawn

from fontTools import ttLib
import matplotlib.font_manager as fontman


TAG_PATTERN = re.compile(r"\\\s*([^(\\]+)(?<!\s)\s*(?:\(\s*([^)]+)(?<!\s)\s*)?")
INT_PATTERN = re.compile(r"^[+-]?\d+")
LINE_PATTERN = re.compile(r"(?:\{(?P<tags>[^}]*)\}?)?(?P<text>[^{]*)")

State = collections.namedtuple("State", ["font", "italic", "weight", "drawing"])

def parse_int(s):
    if match := INT_PATTERN.match(s):
        return int(match.group(0))
    else:
        return 0

def parse_tags(s, state, line_style, styles):
    for match in TAG_PATTERN.finditer(s):
        value, paren = match.groups()

        def get_tag(name, *exclude):
            if value.startswith(name) and not any(value.startswith(ex) for ex in exclude):
                args = []
                if paren is not None:
                    args.append(paren)
                if len(stripped := value[len(name):].lstrip()) > 0:
                    args.append(stripped)
                return args
            else:
                return None


        if (args := get_tag("fn")) is not None:
            if len(args) == 0:
                font = line_style.font
            elif args[0].startswith("@"):
                font = args[0][1:]
            else:
                font = args[0]
            state = state._replace(font=font)
        elif (args := get_tag("b", "blur", "be", "bord")) is not None:
            weight = None if len(args) == 0 else parse_int(args[0])
            if weight is None:
                transformed = None
            elif weight == 0:
                transformed = 400
            elif weight in (1, -1):
                transformed = 700
            elif 100 <= weight <= 900:
                transformed = weight
            else:
                transformed = None

            state = state._replace(weight=transformed or line_style.weight)
        elif (args := get_tag("i", "iclip")) is not None:
            slant = None if len(args) == 0 else parse_int(args[0])
            state = state._replace(italic=slant == 1 if slant in (0, 1) else line_style.italic)
        elif (args := get_tag("p", "pos", "pbo")) is not None:
            scale = 0 if len(args) == 0 else parse_int(args[0])
            state = state._replace(drawing=scale != 0)
        elif (args := get_tag("r")) is not None:
            if len(args) == 0:
                style = line_style
            else:
                if (style := styles.get(args[0])) is None:
                    print(rf"Warning: \r argument {args[0]} does not exist; defaulting to line style")
                    style = line_style
            state = state._replace(font=style.font, italic=style.italic, weight=style.weight)
        elif (args := get_tag("t")) is not None:
            if len(args) > 0:
                state = parse_tags(args[0], state, line_style, styles)

    return state

def parse_line(line, line_style, styles):
    state = line_style
    for tags, text in LINE_PATTERN.findall(line):
        if len(tags) > 0:
            state = parse_tags(tags, state, line_style, styles)
        if len(text) > 0:
            yield state, text

def common_value(array1, array2): 
    array1_set = set(array1) 
    array2_set = set(array2) 
    if (array1_set & array2_set): 
        return True 
    else: 
        return False


def is_mkv(filename):
    with open(filename, 'rb') as f:
        return f.read(4) == b'\x1a\x45\xdf\xa3'

def is_ass(filename):
    with open(filename, 'rb') as f:
        return f.name.endswith(".ass")

def is_writable(path):
    return os.access(path, os.W_OK)


def fonts_name_used(doc, fonts):

    font_list = []

    styles = {style.name: State(style.fontname, style.italic, 700 if style.bold else 400, False)
              for style in doc.styles}

    for i, line in enumerate(doc.events):
        if isinstance(line, ass.Comment):
            continue
        nline = i + 1

        try:
            style = styles[line.style]

        except KeyError:
            print(f"Warning: Unknown style {line.style} on line {nline}; assuming default style")
            style = State("Arial", False, 400, False)

        for state, text in parse_line(line.text, style, styles):
            
            if state.font not in font_list:
                font_list.append(state.font)

    for font in styles:
        if styles[font].font not in font_list:
            font_list.append(styles[font].font)

        
    return font_list

def get_installed_fonts():
    fonts = fontman.win32InstalledFonts(fontext='ttf')

    FONT_SPECIFIER_NAME_ID = 4
    FONT_SPECIFIER_FAMILY_ID = 1
    def font_short_name(font):
        """Get the short name from the font's names table"""
        name = ""
        family = ""
        for record in font['name'].names:
            if b'\x00' in record.string:
                name_str = record.string.decode('utf-16-be')
            else:   
                name_str = record.string.decode('latin-1')
            if record.nameID == FONT_SPECIFIER_NAME_ID and not name:
                name = name_str
            elif record.nameID == FONT_SPECIFIER_FAMILY_ID and not family: 
                family = name_str
            if name and family: break
        return name, family

    font_list = {}

    for i in range(len(fonts)):

        try :
            tt = ttLib.TTFont(fonts[i], fontNumber=0)
        except:
            print(fonts[i])
            break

        font_list[font_short_name(tt)] = fonts[i]

    return font_list

def get_used_font_path(subtitles):
    print("Recovering fonts used in subtitles")

    installedFonts = get_installed_fonts()
    fonts = []
    fonts_path = []

    for name, doc in subtitles:
        print(f"Validating track {name}")
        fontsUsed = fonts_name_used(doc, fonts)

        for fontFullName in installedFonts:  # Pour récupérer le nom et la famille de toutes les fonts

            if common_value(fontFullName, fontsUsed) and installedFonts[fontFullName] not in fonts_path:  # Pour vérifier si le nom ou la famille se trouve dans les fonts utilisées
                    fonts_path.append(installedFonts[fontFullName])

    print("%s fonts found" % len(fonts_path))
    return fonts_path

def merge(ass, mkv, fonts, mkvmerge):
    print("Merging matroska file with fonts")

    output = os.path.basename(mkv).split('.mkv')[0] + ".fontmerge.mkv"

    mkvmerge_args = [
        "-q",
        "--ui-language fr",
        "-o",
        '"' + output + '"',
        '"' + mkv + '"',
        ]

    if mkvmerge :
        mkvmerge_args.insert(0, mkvmerge)
    else:
        mkvmerge_args.insert(0, "mkvmerge")

    for path in fonts:
        
        mkvmerge_args.append("--attachment-name " + '"' + os.path.basename(path) + '"')
        mkvmerge_args.append("--attachment-mime-type application/x-truetype-font ")
        mkvmerge_args.append("--attach-file " + '"' + path + '"')

    subprocess.call(" ".join(mkvmerge_args))


def main():
    parser = argparse.ArgumentParser(description="Automatically merge fonts used in a Matroska file.")
    parser.add_argument('subtitles', help="""
    Subtitles containing fonts to merge. Need to be an ASS file.
    """)
    parser.add_argument('mkv', help="""
    Video where fonts will go. Need to be a Matroska file.
    """)
    parser.add_argument('--mkvmerge', metavar="path", help="""
    Path to mkvmerge.exe if not in environment variable.
    """)

    args = parser.parse_args()  

    if not distutils.spawn.find_executable("mkvmerge.exe") and args.mkvmerge is None:
        return print("fontmerge.py: error: mkvmerge in not in your environnements variable, add it or specify the path to mkvmerge.exe with --mkvmerge.")
    if not is_mkv(args.mkv):
        return print("fontmerge.py: error: the file on -mkv is not a Matroska file.")   
    if not is_ass(args.subtitles):
        return print("fontmerge.py: error: the file is not an Ass file.")
    if not is_writable(args.mkv):
        return print("fontmerge.py: error: unable to create the file.")


    with open(args.subtitles, 'r', encoding='utf_8_sig') as f:
        subtitles = [(os.path.basename(args.subtitles), ass.parse(f))]
    
    fonts_path = get_used_font_path(subtitles)
 
    merge(args.subtitles, args.mkv, fonts_path, args.mkvmerge)

    return print("Successfully merging subtitles and mkv")


if __name__ == "__main__":
    sys.exit(main())