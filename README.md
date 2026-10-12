## ytm

yt-dlp alternative for youtube music

# features

- smooth streaming and downloading
- on demand songs
- more to come

# install

```
pip install "ytm[default] @ git+https://github.com/devmidnightst/ytm"
```

you also want `ffmpeg` on your path for tagging and cover art, and `mpv` (or `ffplay`) for `ytm play`.

# usage

```
ytm daft punk one more time          # search youtube music, grab the top song
ytm https://music.youtube.com/playlist?list=...   # whole album or playlist
ytm play lofi hip hop                # stream it, nothing saved
ytm search the weeknd                # top 10 songs with links
```

no quotes needed, anything that isn't a url gets searched on youtube music.
every yt-dlp option still works and wins over the ytm defaults, e.g. `ytm -o "%(title)s.%(ext)s" song name`.
`ytm --help-all` shows all of them. `YTM_PLAYER=vlc ytm play ...` picks a different player.

what `ytm` does by default:

- keeps the original audio codec (opus, falls back to m4a), so there's no lossy re-encode and no wait on ffmpeg transcoding
- writes artist / album / title / track number tags and embeds square cover art (youtube's 16:9 thumbnails get cropped)
- saves to `Artist/Album/01 Title.opus`
- 4 concurrent fragments on segmented streams and 10 retries
- quiet output: a live progress bar and one `[ytm] saved ...` line per song
- `ytm play` resolves playlist songs one at a time right before they play, so playback starts fast and stream links never expire mid queue

# engine changes (also available through `yt-dlp`)

- `ytmsearch:` / `ytmsearchN:` search prefix for youtube music songs
- `-t music` preset alias with the same audio settings `ytm get` uses
- network errors like proxy, ssl and cut off downloads no longer tell you to file a bug report
- bug reports point at this repo instead of upstream yt-dlp
- `pip install` from git now generates lazy extractors at build time, so startup matches release builds

# credits

the engine in `yt_dlp/` is [yt-dlp](https://github.com/yt-dlp/yt-dlp) 2026.08.19, released into the public domain under the unlicense (see `UNLICENSE-yt-dlp.txt`). the upstream readme is kept in `README.yt-dlp.md`.
