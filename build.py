"""Build on the OS you intend to distribute for."""
import os
import platform
from pathlib import Path
import PyInstaller.__main__

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    icon = root / 'assets' / ('JitterGPS.ico' if platform.system() == 'Windows' else 'JitterGPS.icns')
    args = [str(root / 'main.py'), '--name=JitterGPS', '--noconfirm',
            '--icon=' + str(icon),
            # PyInstaller splits add-data on os.pathsep: ';' on Windows, ':' elsewhere.
            '--add-data=' + str(root / 'assets/JitterGPS.png') + os.pathsep + 'assets',
            '--clean', '--windowed', '--collect-all=customtkinter',
            '--collect-all=tkintermapview',
            '--distpath=' + str(root / 'dist'), '--workpath=' + str(root / 'build'),
            '--specpath=' + str(root)]
    if platform.system() == 'Windows':
        args.append('--onefile')
    else:
        args.append('--onedir')
    PyInstaller.__main__.run(args)
