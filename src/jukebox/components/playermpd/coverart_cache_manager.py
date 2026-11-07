import os
import jukebox.cfghandler

cfg = jukebox.cfghandler.get_handler('jukebox')


class CoverartCacheManager:
    def __init__(self):
        coverart_cache_path = cfg.setndefault('webapp', 'coverart_cache_path', value='../../src/webapp/build/cover-cache')
        self.cache_folder_path = os.path.expanduser(coverart_cache_path)

    def find_file_by_hash(self, hash_value):
        """Return the cached file whose name (without extension) is exactly ``hash_value``, or None"""
        # Compare the whole name: a prefix match would e.g. return the cover of 'folge-10' for 'folge-1'
        for filename in os.listdir(self.cache_folder_path):
            if os.path.splitext(filename)[0] == hash_value:
                return filename
        return None

    def save_to_cache(self, base_filename, album_art_data):
        # MPD only sends 'type' if it knows the MIME type
        mime_type = album_art_data.get('type', 'image/jpeg')
        file_extension = 'jpg' if mime_type == 'image/jpeg' else mime_type.split('/')[-1]
        cache_filename = f"{base_filename}.{file_extension}"

        with open(os.path.join(self.cache_folder_path, cache_filename), 'wb') as file:
            file.write(album_art_data['binary'])

        return cache_filename
