#
# Copyright (c) 2020, msdm
# 
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
# 
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name of rhythmdbsync nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

help_str = '''
A tool to import ID3 ratings (Popularities) to Rhythmbox database, and export
the ratings from the database to the actual files.
    
Usage:
    rhythmdbsync [options] import
        Import the ID3 ratings from files to the database. If a POPM ID3 frame
        exists in the file metadata with the 'Rhythmbox' as its email string,
        it will be imported. Otherwise, any other POPM frame set by other
        applications will be imported.
        
    rhythmdbsync [options] export
        Export the ratings from the database to the actual files.
    
Options:
    -h, --help
        Show this page.
        
    -i <file>, --input-file=<file>
        Specify the input Rhythmbox database file. If not provided,
        ~/.local/share/rhythmdb.xml will be used by default.
        
    -o <file>, --output-file=<file>
        Specify the output Rhythmbox database file. If not provided, the input
        file will be overwritten. This option is only used for imporing.
        
    --force
        By default, the ratings will not be imported/exported if a rating is
        already exists in the destination for that specific item. Providing
        --force option will cause to import/exports the ratings regardless of
        the existence of a rating in the destination.
        
    --log-file=<file>
        The file that the logs will be stored in it. If not provided, logging
        will be disabled.
        
    --log-level=[critical|error|warning|info|debug]
        The logging level. The default level is "warning".
        
    --dry
        Providing this option will not save the import/export result in the
        files. This is useful to evaluate what will happen after the actual
        import/export.
'''

import eyed3
import eyed3.id3.tag
import io
import logging
import xml.etree.ElementTree as et
import pathlib
import urllib.parse as url
import sys, getopt

log_levels = {
    'critical': logging.CRITICAL,
    'error'   : logging.ERROR,
    'warning' : logging.WARNING,
    'info'    : logging.INFO,
    'debug'   : logging.DEBUG}


def stars2rating(stars):
    ratings = {0: 0, 1: 1, 2: 64, 3: 128, 4: 196, 5: 255}
    if stars in ratings:
        return ratings[stars] 
    else:
        raise ValueError('Uknown stars value: {}'.format(stars))
        
def rating2stars(rating):
    if rating < 1:
        return 0
    if rating < 32:
        return 1
    if rating < 96:
        return 2
    if rating < 160:
        return 3
    if rating < 224:
        return 4
    if rating <= 255:
        return 5
    
    raise ValueError('Uknown stars value: {}'.format(rating))
            
class Popularities(eyed3.id3.tag.PopularitiesAccessor):
    def __init(self, fs):
        super().__init__(fs)
        
    def get_all(self):
        flist = self._fs[eyed3.id3.tag.frames.POPULARITY_FID] or []
        fl = dict()
        for popm in flist:
            fl[popm.email.decode('utf8')] = {
                'rating': popm.rating,
                'play_count': popm.count}
        return fl
        
    def set(self, rating, play_count):
        super().set('Rhythmbox', rating, play_count)
        
    def remove(self, ):
        super().remove('Rhythmbox')
        

class Audio:
    def __init__(self, path):
        self.path = path
        self.audio_file = eyed3.load(self.path)
        
        #TODO: Does it mean the MP3 file lacks metadata when its tag list 
        # is Nonetype? Should we create metadata from the scratch?
        if self.audio_file is None or self.audio_file.tag is None:
            raise ValueError('Unsupported file "{}"'.format(self.path))
            
        self._popularities = Popularities(self.audio_file.tag.frame_set)
        pops = self._popularities.get_all()
        
        self._is_dirty = False
        self._rating = 0
        self._play_count = 0

        email = None
        if pops:
            if 'Rhythmbox' in pops:
                email = 'Rhythmbox'
            else:
                email = list(pops.keys())[0]
                if len(pops) > 1:
                    logging.info('Multiple ratings were found for "{}". Getting from the first one ({})'.format(self.path, email))
                else:
                    logging.info('Getting the rating from {} for "{}".'.format(email, self.path))

            if email is not None:
                self._rating = pops[email]['rating']
                self._play_count = pops[email]['play_count']
                
        self._imported_email = email
    
    @property
    def rating(self):
        return self._rating
    
    def set_rating(self, rating, force=False):
        if force:
            if self._rating != rating:
                self._rating = rating
                self._is_dirty = True
        else:    
            if self._rating == 0 and rating != 0:
                self._rating = rating
                self._is_dirty = True
    
    @property
    def stars(self):
        return rating2stars(self._rating)  
        
    def set_stars(self, stars, force=False):
        self.set_rating(stars2rating(stars), force=force)
            
    @property
    def play_count(self):
        return self._play_count
    
    def set_play_count(self, count, force=False):
        if force:
            if self._play_count != count:
                self._play_count = count
                self._is_dirty = True
        else:    
            if self._play_count == 0 and count != 0:
                self._play_count = count
                self._is_dirty = True
    
    def save(self):
        if self._imported_email == 'Rhythmbox':
            if self._is_dirty:
                if self._rating == 0:
                    self._popularities.remove()
                else:
                    self._popularities.set(self._rating, self._play_count)
                    
                self.audio_file.tag.save()
                self._is_dirty = False
                return True
        elif self._rating != 0:
            self._popularities.set(self._rating, self._play_count)
            self.audio_file.tag.save()
            return True
            
        return False
        
class Song:
    def __init__(self, element):
        self._element = element
        
    def _get_property(self, prop):
        subelement = self._element.find(prop)
        return None if subelement is None else subelement.text
        
    def _set_property(self, prop, value, force):
        subelement = self._element.find(prop)
        if subelement is not None:
            if not force:
                return False
            
            if not value:
                self._element.remove(subelement)
                return True
        else:
            if not value:
                return False

            #print('Inserting {} for {}'.format(prop, self._element.find('title').text))
            subelement = et.Element(prop)
            last_seen = self._element.find('last-seen')
            if last_seen is not None:
                self._element.insert(list(self._element).index(last_seen) + 1, subelement)
            else:
                self._element.append(subelement)
        
        if subelement.text == value:
            return False
            
        subelement.text = value
        return True
        
    def _uri2path(self, uri):
        return url.unquote(url.urlparse(uri).path)
    
    @property
    def title(self):
        return self._get_property('title')
        
    @title.setter
    def title(self, title):
        self._set_property('title', title)
        
    @property
    def path(self):
        uri = self._get_property('location')
        return None if uri is None else self._uri2path(uri)
        
    @property
    def rating(self):
        rating = self._get_property('rating')
        return 0 if rating is None else int(rating)
        
    def set_rating(self, rating, force=False):
        _rating = None if rating == 0 else str(rating)
        return self._set_property('rating', _rating, force)
        
    @property
    def play_count(self):
        count = self._get_property('play-count')
        return 0 if count is None else int(count)
        
    def set_play_count(self, count, force=False):
        _count = None if count == 0 else str(count)
        return self._set_property('play-count', _count, force)
        

class Rbdb:
    def __init__(self, filename):
        self.path = filename
        self.xml_file = et.parse(filename)
        self.root = self.xml_file.getroot()
        
        #self.xml_file.set('version', '1.0')
        #self.xml_file.set('standalone', 'yes')
        
    def get_songs(self):
        songs = list()
        for element in self.root:
            #TODO: What about other types? (ignore, album, etc.)
            if element.tag == 'entry' and element.get('type') == 'song':
                songs.append(Song(element))
                    
        return songs
        
    def save(self, filename):
        self.reformat()
        #ET.dump(self.xml_file)
        #self.xml_file.write(self.path + 'sss', encoding="UTF-8", xml_declaration=True)
        with open(filename, 'wb+') as f:
            f.write('<?xml version="1.0" standalone="yes"?>\n'.encode())
            f.write(et.tostring(self.root, xml_declaration=False, short_empty_elements=False))
                
    def reformat(self, elem=None, level=0):
        if elem is None:
            elem = self.root
        
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.reformat(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
                


def init_config():
    config  = {
        'input-file':  '',
        'output-file': '',
        'force': False,
        'log-file': '',
        'log-level': logging.WARNING,
        'dry': False}
    
    return config
 
    
def read_options(config):
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:o:f', ['help', 'input-file=', 'output-file=', 'force', 'log-file=', 'log-level=', 'dry'])
    except getopt.GetoptError:
        print(help_str)
        exit(2)
        
    for opt, value in opts:
        if opt in ('-h', '--help'):
            print(help_str)
            exit()
        elif opt in ('-i', '--input-file'):
            config['input-file'] = value
        elif opt in ('-o', '--output-file'):
            config['output-file'] = value
        elif opt in ('-f', '--force'):
            config['force'] = True
        elif opt == '--log-file':
            config['log-file'] = value
        elif opt == '--log-level':
            global log_levels
            if value in log_levels:
                config['log-level'] = log_levels[value]
        elif opt == '--dry':
            config['dry'] = True
            
    #TODO: Maybe these validations should be moved to main()
    if len(args) == 1 and args[0] in ('import', 'export'):
        config['type'] = args[0]
    else:
        print(help_str)
        exit(2)
        
    if not config['input-file']:
        default_dbfile = '~/.local/share/rhythmbox/rhythmdb.xml'
        path = pathlib.PosixPath(default_dbfile).expanduser()
        if path.exists():
            print('No input file was provided. Using the default one from "{}"'.format(default_dbfile))
            config['input-file'] = str(path)
        else:
            print('File "{}" was not found. Please provide the Rhythmbox database file manually.'.format(default_dbfile))
            exit(2)
        
    if not config['output-file'] and config['type'] == 'import':
        ans = input('No output file was provided. The input file will be overwritten. Are you sure? (yes/No) ')
        if ans.lower() in ('y', 'yes'):
            config['output-file'] = config['input-file']
        else:
            exit()


def main():
    config = init_config()
    read_options(config)
    
    if config['log-file']:
        logging.basicConfig(
            filename=config['log-file'], level=config['log-level'], filemode='w')
    else:
        # Prevent eyed3 logs to be printed in stdout.
        log_stream = io.StringIO()
        logging.basicConfig(stream=log_stream)

    logging.debug('Loading the database: {}'.format(config['input-file']))
    rbdb = Rbdb(config['input-file'])
    
    n_items = 0
    n_changed = 0
    if config['type'] == 'import':
        print('Importing the ratings to the library...')
    else:
        print('Exporting the ratings to the files...')

    for song in rbdb.get_songs():
        logging.debug('Loading "{}"'.format(song.path))
        try:
            af = Audio(song.path)
        except IOError:
            logging.warning('File "{}" was not found. Ignoring.'.format(song.path))
            continue
            
        except ValueError:
            logging.warning('Unsupported file type "{}". Ignoring.'.format(song.path))
            continue

        n_items += 1
        if config['type'] == 'import':
            logging.debug('Importing the rating')
            print('\r{} out of {} library items {} updated.'
                .format(n_changed, n_items, 'was' if n_changed == 1 else 'were'), end='')
            rres = song.set_rating(af.stars, force=config['force'])
            pres = song.set_play_count(af.play_count, force=config['force'])
        
            if rres or pres:
                n_changed += 1
                logging.info('"{}" was updated. Rating: {}, Play count: {}'.format(song.title, song.rating, song.play_count))
            else:
                logging.info('"{}" already has a rating in the library.'.format(song.title))
        else:
            logging.debug('Exporing the rating')
            af.set_stars(song.rating, force=config['force'])
            af.set_play_count(song.play_count, force=config['force'])
            
            if config['dry']:
                n_changed += 1
                logging.info('"{}" was supposed to be updated. Rating: {}, Play count: {}'.format(af.path, af.rating, af.play_count))
            elif af.save():
                n_changed += 1
                logging.info('{} was updated. Rating: {}, Play count: {}'.format(af.path, af.rating, af.play_count))

            print('\r{} files out of {} library items {} updated.'
                .format(n_changed, n_items, 'was' if n_changed == 1 else 'were'), end='')
        
    print('')
    if config['type'] == 'import' and not config['dry']:
        rbdb.save(config['output-file'])
        
        
if __name__ == '__main__':
    main()
