import os
import subprocess
import sys
import warnings

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class LazyExtractorsHook(BuildHookInterface):
    """Generate yt_dlp/extractor/lazy_extractors.py at build time

    Without it every run imports all ~1800 extractor modules up front.
    Release builds of upstream yt-dlp generate it with `make`, but plain
    `pip install git+...` installs never did, so they started much slower"""

    PLUGIN_NAME = 'custom'

    def initialize(self, version, build_data):
        # Editable installs would go stale as soon as an extractor is edited
        if version == 'editable' or os.environ.get('YTDLP_NO_LAZY_EXTRACTORS'):
            return
        script = os.path.join(self.root, 'devscripts', 'make_lazy_extractors.py')
        if not os.path.isfile(script):
            return
        try:
            subprocess.run([sys.executable, script], cwd=self.root, check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            warnings.warn(f'Could not generate lazy extractors, startup will be slower: {e}', stacklevel=1)
