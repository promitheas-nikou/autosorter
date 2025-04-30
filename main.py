#!/usr/bin/env python3
import argparse
from pathlib import Path
import logging
import re
from mutagen import File
import shutil
import re
import pickle

CONFIG_PREPEND_TRACKNUM = True
CONFIG_SPLIT_IN_ALBUM_DIRECTORIES = True
CONFIG_VALID_NUMBER_DELIMETERS = [',','_','/',';']

def split_by_any(s, delimiters):
    pattern = f"[{re.escape(''.join(delimiters))}]"
    return re.split(pattern, s)

def extract_metadata(file_path):
    audio = File(file_path, easy=True)
    if audio is None:
        return None

    metadata = {
        "title": audio.get("title", [None])[0],
        "artist": audio.get("artist", [None])[0],
        "album": audio.get("album", [None])[0],
        "tracknumber": audio.get("tracknumber", [None])[0],
        "genre": audio.get("genre", [None])[0],
        "date": audio.get("date", [None])[0],
        "albumartist": audio.get("albumartist", [None])[0],
        "discnumber": audio.get("discnumber", [None])[0],
    }
    alternative_tags = {
        "ISRC": ["TSRC"],  # International Standard Recording Code
        "encoder": ["TSSE"],  # Encoding software/hardware used
        "source_url": ["WOAS"],  # Official audio source URL
        "genre": ["TCON"],
        "date": ["TDRC"],
        "comment": ["COMM"]
    }
    """
    for key, tag_list in alternative_tags.items():
        for tag in tag_list:
            value = audio.tags.get(tag)
            if value:
                metadata[key] = value.text[0]
                break  # Only add first found tag
    """
    return metadata

MUSIC_FILE_SUFFIXES = [".mp3", ".ogg", ".flac", ".m4a"]
entries = {}

def check_add_entry(art,alb,tit,v):
    k=(art,alb,tit)
    if k in entries:
        return False
    entries[k]=str(v)
    return True

def sanitize_path(path_str):
    # Define a regex pattern for invalid characters in paths
    invalid_chars = r'[<>:"/\\\|\*\x00-\x1F]'
    sanitized = re.sub(invalid_chars, '_', path_str)
    return sanitized.strip()

def sort_file(fp, op):
    md = extract_metadata(fp)
    logger.debug(f'Sorting music {fp} ({md['title']} by {md['artist']})')
    Artist = md['albumartist']
    if Artist==None:
        Artist = 'Unknown Artist'
        logger.warning(f"Missing artist info on file {fp}")
    artist_path = sanitize_path(Artist)
    Album = md['album']
    if Album==None:
        Album = 'Unknown Album'
        logger.warning(f"Missing album info on file {fp}")
    album_path = sanitize_path(Album)
    Title = md['title']
    if Title==None:
        Title = f'Unknown Title {randomcounter}'
        randomcounter+=1
        logger.warning(f"Missing title on file {fp}")
        tfn = sanitize_path(fp.stem)
    Number = md['tracknumber']
    Disc = md['discnumber']
    if CONFIG_PREPEND_TRACKNUM and Number!=None:
        tfn = sanitize_path(f"{'' if Disc==None else f'{split_by_any(Disc,CONFIG_VALID_NUMBER_DELIMETERS)[0]}-'}{split_by_any(Number,CONFIG_VALID_NUMBER_DELIMETERS)[0]} - {Title}")
    else:
        tfn = sanitize_path(Title)
    if CONFIG_SPLIT_IN_ALBUM_DIRECTORIES:
        nfp = op / artist_path / album_path / (tfn+fp.suffix)
    else:
        nfp = op / artist_path / (tfn+fp.suffix)
    logger.info(f"Sorting file {fp}...")
    if not check_add_entry(artist_path,album_path,tfn,nfp):
        logger.warning(f"SKIPPING FILE {fp}: ALREADY EXISTS AT {entries[(artist_path,album_path,tfn)]}")
    else:
        nfp.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(fp,nfp)
        logger.debug(f"Copying: {fp} -> {nfp}")



def sort_dir(id,od):
    op = Path(od)
    for filepath in Path(id).rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix not in MUSIC_FILE_SUFFIXES:
            continue
        sort_file(filepath,op)
        

def setup_logs():
    global logger
    formatstr='[%(asctime)s - %(levelname)s] - %(message)s'
    logger = logging.getLogger('autosorter')
    logger.setLevel(logging.DEBUG)

    # Create console handler with a lower level (e.g., INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARN)  # Console logs at INFO level

    # Create file handler with a higher level (e.g., DEBUG)
    file_handler = logging.FileHandler('autosorter.log')
    file_handler.setLevel(logging.DEBUG)  # File logs at DEBUG level

    formatter = logging.Formatter(formatstr)
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info('Starting!')

if __name__=="__main__":
    setup_logs()
    parser = argparse.ArgumentParser(description="Music File Autosorter")
    parser.add_argument('--input','-i',dest='input',type=Path,required=True,help="Input directory of music files")
    parser.add_argument('--output','-o',dest='output',type=Path,required=True,help="Output directory of sorted music files")
    parser.add_argument('--prepend-track-number',dest='prepend_tracknum',required=False,action='store_true',help="If included, will prepend the track number and disc number before the name of each file (when available)")
    parser.add_argument('--dont-split-albums',dest='split_album',required=False,action='store_false',help="If included, will dump all music files in the artist directory, not in an album subdirectory")
    parser.add_argument('--entries','-e',dest='entries_file',type=Path,default=Path('entries.pkl'),help="The path to the entries .pkl file that stores the current sorted files (default: 'entries.pkl')")
    args = parser.parse_args()
    CONFIG_PREPEND_TRACKNUM = args.prepend_tracknum
    CONFIG_SPLIT_IN_ALBUM_DIRECTORIES = args.split_album
    entriespath = args.entries_file.resolve()
    if entriespath.is_dir():
        logger.critical("ENTRIES FILEPATH IS A DIRECTORY! QUITTING!")
        exit(1)
    entriespath.parent.mkdir(parents=True,exist_ok=True)
    if entriespath.exists():
        with open(entriespath,'rb') as f:
            entries = pickle.load(f)
    try:
        sort_dir(args.input,args.output)
        with open(entriespath,'wb') as f:
            pickle.dump(entries, f)
    except Exception as e:
        logger.critical('ENCOUNTERED UNEXPECTED ERROR!!!')
        logger.critical(str(e))
        logger.critical('DUMPING CURRENT TABLE TO BACKUP FILE')
        with open(entriespath.with_suffix(entriespath.suffix+'.bak'),'wb') as f:
            pickle.dump(entries, f)