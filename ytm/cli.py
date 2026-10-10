"""Command line front-end for ytm

    ytm [get] QUERY|URL... [yt-dlp options]   download songs as tagged audio
    ytm play QUERY|URL...  [yt-dlp options]   stream audio through mpv/ffplay
    ytm search QUERY       [yt-dlp options]   list the top YouTube Music songs

Anything that is not a URL is looked up on YouTube Music, so
`ytm daft punk one more time` works without quotes. Every yt-dlp
option is still accepted and wins over the ytm defaults.
"""

import os
import re
import shutil
import subprocess
import sys

COMMANDS = ('get', 'play', 'search')

OUTTMPL = (
    '%(artist,artists.0,creator,uploader|Unknown Artist)s/'
    '%(album|Singles)s/'
    '%(track_number&{:02d} |)s%(track,title)s.%(ext)s')

DONE_TEMPLATE = 'after_move:[ytm] saved %(filepath)q'

SEARCH_TEMPLATE = (
    '%(playlist_index)2d. %(title)s'
    '%(artists.0,channel,uploader& - {}|)s'
    '%(duration_string& [{}]|)s  %(url)s')

DEFAULTS = {
    'get': [
        '--preset-alias', 'music',
        '--output', OUTTMPL,
        '--concurrent-fragments', '4',
        '--retries', '10', '--fragment-retries', '10',
        '--quiet', '--progress', '--no-simulate',
        '--print', DONE_TEMPLATE,
    ],
    'search': [
        '--flat-playlist', '--quiet', '--print', SEARCH_TEMPLATE,
    ],
    'play': [
        '--format', 'ba[acodec=opus]/ba[ext=m4a]/ba/b',
        '--flat-playlist', '--quiet', '--no-warnings',
    ],
}

SEARCH_RESULTS = {'get': 1, 'play': 1, 'search': 10}

# "scheme:" / "ytsearch5:" style prefixes, or something that looks like a domain with a path
_URL_RE = re.compile(r'^(?:[a-zA-Z][\w+.-]*:|[\w-]+(?:\.[\w-]+)+/)')

USAGE = __doc__.split('\n\n', 1)[1].rstrip() + '\n\nRun `ytm --help-all` for the full list of yt-dlp options.\n'


def is_url(token):
    return bool(_URL_RE.match(token)) or os.path.isfile(token)


def rewrite_urls(urls, command='get'):
    """Turn free text into YouTube Music search URLs

    Consecutive bare words are joined into a single query so quoting is optional"""
    n = SEARCH_RESULTS[command]
    result, words = [], []

    def flush():
        if words:
            result.append(f'ytmsearch{n}:{" ".join(words)}')
            words.clear()

    for token in urls:
        if is_url(token):
            flush()
            result.append(token)
        else:
            words.append(token)
    flush()
    return result


def split_command(argv):
    if argv and argv[0] in COMMANDS:
        return argv[0], argv[1:]
    return 'get', argv


def build_argv(command, args):
    # User arguments go last so they override the defaults
    return [*DEFAULTS[command], *args]


def find_player():
    if custom := os.environ.get('YTM_PLAYER'):
        return custom
    return next((name for name in ('mpv', 'ffplay') if shutil.which(name)), None)


def player_command(player, url, title=None, headers=None):
    headers = headers or {}
    name = os.path.basename(player).lower()
    if name.startswith('mpv'):
        cmd = [player, '--no-video', '--really-quiet']
        if title:
            cmd.append(f'--force-media-title={title}')
        if ua := headers.get('User-Agent'):
            cmd.append(f'--user-agent={ua}')
        if referer := headers.get('Referer'):
            cmd.append(f'--referrer={referer}')
    elif name.startswith('ffplay'):
        cmd = [player, '-nodisp', '-autoexit', '-loglevel', 'error']
        if title:
            cmd += ['-window_title', title]
        if ua := headers.get('User-Agent'):
            cmd += ['-user_agent', ua]
        if referer := headers.get('Referer'):
            cmd += ['-headers', f'Referer: {referer}\r\n']
    else:
        cmd = [player]
    return [*cmd, url]


def _iter_entries(info):
    if info.get('_type') in ('playlist', 'multi_video'):
        for entry in info.get('entries') or []:
            if entry:
                yield from _iter_entries(entry)
    else:
        yield info


def play(argv):
    from yt_dlp import YoutubeDL, parse_options

    player = find_player()
    if not player:
        sys.exit('ERROR: ytm play needs mpv or ffplay on PATH (or set YTM_PLAYER)')

    _, _, urls, ydl_opts = parse_options(build_argv('play', argv))
    urls = rewrite_urls(urls, 'play')
    if not urls:
        sys.exit(USAGE)

    with YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            for entry in _iter_entries(ydl.extract_info(url, download=False)):
                # Playlists are extracted flat, so each song is only resolved right
                # before it plays. Playback starts fast and stream URLs never go stale
                if entry.get('_type') == 'url':
                    entry = ydl.extract_info(entry['url'], download=False)
                if not entry.get('url'):
                    ydl.report_warning(f'No playable stream for {entry.get("title") or entry.get("id")}')
                    continue
                title = ' - '.join(filter(None, (entry.get('artist') or entry.get('uploader'), entry.get('title'))))
                print(f'[ytm] playing {title}', file=sys.stderr)
                ret = subprocess.call(player_command(player, entry['url'], title, entry.get('http_headers')))
                if ret < 0 or ret == 130:  # killed by Ctrl+C
                    return 130
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv in (['-h'], ['--help']) or argv[0] == 'help':
        print(USAGE)
        sys.exit(0)
    if argv == ['--help-all']:
        argv = ['--help']

    command, args = split_command(argv)
    if command == 'play':
        try:
            sys.exit(play(args))
        except KeyboardInterrupt:
            sys.exit('\nERROR: Interrupted by user')

    import yt_dlp
    yt_dlp.main(build_argv(command, args), url_hook=lambda urls: rewrite_urls(urls, command))
