import asyncio
import os
import shutil
from typing import Any


async def check_virtual_display() -> dict[str, Any]:
    display = os.getenv('DISPLAY')
    if not display:
        return {
            'configured': False,
            'ready': None,
            'display': None,
        }

    xdpyinfo = shutil.which('xdpyinfo')
    if not xdpyinfo:
        return {
            'configured': True,
            'ready': None,
            'display': display,
            'error': 'xdpyinfo not available',
        }

    proc = await asyncio.create_subprocess_exec(
        xdpyinfo,
        '-display',
        display,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()

    return {
        'configured': True,
        'ready': proc.returncode == 0,
        'display': display,
    }
