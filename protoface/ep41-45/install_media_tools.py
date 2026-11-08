"""Use imageio-ffmpeg's bundled executable without a blocking system package install."""
from pathlib import Path
import os
import imageio_ffmpeg


def main():
    folder = Path(os.environ['RUNNER_TEMP']) / 'thirteen-doors-media-tools'
    folder.mkdir(exist_ok=True)
    link = folder / 'ffmpeg'
    target = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if link.is_symlink() and link.resolve() != target.resolve():
        link.unlink()
    if not link.exists():
        link.symlink_to(target)
    with open(os.environ['GITHUB_PATH'], 'a') as handle:
        handle.write(str(folder) + '\n')
    print('Bundled ffmpeg is available for native clip normalization.')


if __name__ == '__main__':
    main()
