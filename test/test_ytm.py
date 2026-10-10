#!/usr/bin/env python3

# Allow direct execution
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import base64
import shutil
import subprocess
import tempfile

from yt_dlp import YoutubeDL, parse_options
from yt_dlp.extractor.youtube import YoutubeMusicSearchIE
from yt_dlp.networking.exceptions import ProxyError, SSLError
from yt_dlp.utils import ExtractorError
from ytm.cli import build_argv, player_command, rewrite_urls, split_command


class TestYtmCli(unittest.TestCase):
    def test_bare_words_become_one_search(self):
        self.assertEqual(rewrite_urls(['daft', 'punk', 'one', 'more', 'time']), ['ytmsearch1:daft punk one more time'])

    def test_urls_are_kept(self):
        self.assertEqual(rewrite_urls([
            'https://music.youtube.com/watch?v=abcdefghijk', 'lofi', 'beats', 'ytsearch3:x', 'youtu.be/abcdefghijk',
        ], 'search'), [
            'https://music.youtube.com/watch?v=abcdefghijk', 'ytmsearch10:lofi beats', 'ytsearch3:x', 'youtu.be/abcdefghijk',
        ])

    def test_split_command(self):
        self.assertEqual(split_command(['play', 'a']), ('play', ['a']))
        self.assertEqual(split_command(['a', 'b']), ('get', ['a', 'b']))
        self.assertEqual(split_command([]), ('get', []))

    def test_user_options_override_defaults(self):
        _, _, urls, ydl_opts = parse_options(build_argv('get', ['-o', 'x.%(ext)s', '--no-quiet', 'song']))
        self.assertEqual(urls, ['song'])
        self.assertEqual(ydl_opts['outtmpl']['default'], 'x.%(ext)s')
        self.assertFalse(ydl_opts['quiet'])
        self.assertEqual(ydl_opts['concurrent_fragment_downloads'], 4)

    def test_search_is_simulated(self):
        _, _, _, ydl_opts = parse_options(build_argv('search', ['x']))
        self.assertTrue(ydl_opts['simulate'])
        self.assertEqual(ydl_opts['extract_flat'], 'in_playlist')

    def test_player_command(self):
        cmd = player_command('mpv', 'https://x/a', 'A - B', {'User-Agent': 'UA, with comma'})
        self.assertEqual(cmd, ['mpv', '--no-video', '--really-quiet', '--force-media-title=A - B', '--user-agent=UA, with comma', 'https://x/a'])
        self.assertEqual(player_command('ffplay', 'u')[-1], 'u')
        self.assertEqual(player_command('/opt/vlc', 'u'), ['/opt/vlc', 'u'])


class TestMusicEngine(unittest.TestCase):
    def test_music_preset(self):
        _, _, _, ydl_opts = parse_options(['-t', 'music', 'x'])
        self.assertEqual(ydl_opts['format'], 'ba[acodec=opus]/ba[ext=m4a]/ba/b')
        keys = [pp['key'] for pp in ydl_opts['postprocessors']]
        for key in ('FFmpegExtractAudio', 'FFmpegMetadata', 'EmbedThumbnail', 'FFmpegThumbnailsConvertor'):
            self.assertIn(key, keys)
        extract = next(pp for pp in ydl_opts['postprocessors'] if pp['key'] == 'FFmpegExtractAudio')
        self.assertEqual(extract['preferredcodec'], 'best')

    def test_ytmsearch_key(self):
        self.assertTrue(YoutubeMusicSearchIE.suitable('ytmsearch5:some song'))
        self.assertTrue(YoutubeMusicSearchIE.suitable('ytmsearch:some song'))
        self.assertFalse(YoutubeMusicSearchIE.suitable('ytsearch:some song'))

    def test_network_errors_are_expected(self):
        for exc in (ProxyError('tunnel failed'), SSLError('bad handshake')):
            try:
                raise exc
            except type(exc) as e:
                err = ExtractorError('Unable to download webpage', cause=e)
            self.assertTrue(err.expected, type(exc).__name__)
            self.assertNotIn('report this issue', str(err))
        self.assertIn('report this issue', str(ExtractorError('unexpected')))


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg is needed')
class TestMusicDownload(unittest.TestCase):
    def test_tagged_opus_with_square_cover(self):
        try:
            import mutagen
            from mutagen.flac import Picture
        except ImportError:
            self.skipTest('mutagen is needed')

        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=duration=1',
                            '-c:a', 'libopus', os.path.join(d, 'song.webm')], check=True)
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=640x360',
                            '-frames:v', '1', os.path.join(d, 'thumb.webp')], check=True)
            _, _, _, ydl_opts = parse_options(build_argv('get', ['--enable-file-urls', '--no-progress', '-P', d]))
            info = {
                'id': 'abcdefghijk', 'title': 'Song (Official Audio)', 'track': 'Song', 'artist': 'Artist',
                'album': 'Album', 'track_number': 3, 'extractor': 'youtube', 'extractor_key': 'Youtube',
                'webpage_url': 'https://music.youtube.com/watch?v=abcdefghijk',
                'formats': [
                    {'format_id': '251', 'url': f'file://{d}/song.webm', 'ext': 'webm', 'acodec': 'opus', 'vcodec': 'none'},
                    {'format_id': '18', 'url': f'file://{d}/song.webm', 'ext': 'mp4', 'acodec': 'mp4a.40.2', 'vcodec': 'avc1'},
                ],
                'thumbnails': [{'url': f'file://{d}/thumb.webp', 'id': '0'}],
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.process_ie_result(info, download=True)

            path = os.path.join(d, 'Artist', 'Album', '03 Song.opus')
            self.assertTrue(os.path.isfile(path))
            tags = mutagen.File(path)
            self.assertEqual(tags['artist'], ['Artist'])
            self.assertEqual(tags['album'], ['Album'])
            cover = Picture(base64.b64decode(tags['metadata_block_picture'][0]))
            self.assertEqual((cover.width, cover.height), (360, 360))


if __name__ == '__main__':
    unittest.main()
