import os
import shutil
from pathlib import Path


def main():
    src_dir = Path(__file__).parent / 'agents'
    dest_dir = Path.home() / '.ghccli' / 'agents'
    dest_dir.mkdir(parents=True, exist_ok=True)

    for file in src_dir.iterdir():
        if file.is_file() and file.suffix in {'.md', '.yaml'}:
            shutil.copy2(file, dest_dir / file.name)
            print(f'Copied {file.name} to {dest_dir}')

if __name__ == '__main__':
    main()
