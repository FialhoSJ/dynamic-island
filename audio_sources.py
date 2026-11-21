"""Detecta som nas saídas do Windows, mesmo sem metadados de mídia."""

import os
import time

import comtypes
from pycaw.constants import AudioSessionState, DEVICE_STATE, EDataFlow
from pycaw.pycaw import AudioSession, AudioUtilities, IAudioMeterInformation, IAudioSessionControl2


APP_NAMES = {
    'chrome': 'Google Chrome',
    'msedge': 'Microsoft Edge',
    'firefox': 'Firefox',
    'spotify': 'Spotify',
    'vlc': 'VLC',
    'discord': 'Discord',
    'steam': 'Steam',
    'wmplayer': 'Windows Media Player',
}


def friendly_app_name(session):
    """Usa o nome da sessão; se faltar, usa o executável associado."""
    try:
        display = (session.DisplayName or '').strip()
        if display and not display.startswith('@%'):
            return display
        process = session.Process
        if process:
            stem = os.path.splitext(process.name())[0]
            return APP_NAMES.get(stem.lower(), stem.replace('_', ' ').title())
    except Exception:
        pass
    return ''


class AudioActivityProbe:
    """Mede o pico de cada saída e identifica sessões ativas nessa saída."""

    def __init__(self):
        self.outputs = []
        self.refresh_at = 0

    def _refresh_outputs(self):
        self.outputs = []
        devices = AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
        for device in devices:
            try:
                interface = device._dev.Activate(
                    IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None
                )
                meter = interface.QueryInterface(IAudioMeterInformation)
                self.outputs.append((device, meter))
            except Exception:
                continue
        self.refresh_at = time.monotonic() + 5

    @staticmethod
    def _active_apps(device):
        names = set()
        try:
            enumerator = device.AudioSessionManager.GetSessionEnumerator()
            for index in range(enumerator.GetCount()):
                control = enumerator.GetSession(index)
                if not control:
                    continue
                try:
                    session = AudioSession(control.QueryInterface(IAudioSessionControl2))
                    if session.State == AudioSessionState.Active:
                        name = friendly_app_name(session)
                        if name:
                            names.add(name)
                except Exception:
                    continue
        except Exception:
            return []
        return sorted(names)

    def snapshot(self):
        if time.monotonic() >= self.refresh_at or not self.outputs:
            self._refresh_outputs()
        loudest = None
        for device, meter in self.outputs:
            try:
                peak = float(meter.GetPeakValue())
                if loudest is None or peak > loudest[1]:
                    loudest = (device, peak)
            except Exception:
                self.refresh_at = 0
        if loudest is None or loudest[1] < .015:
            return None

        device, peak = loudest
        apps = self._active_apps(device)
        if len(apps) == 1:
            title, artist, source = apps[0], 'Áudio em reprodução', apps[0]
        elif apps:
            title, artist, source = 'Áudio em reprodução', ', '.join(apps[:3]), 'Áudio do Windows'
        else:
            title, artist, source = 'Áudio em reprodução', 'Saída de áudio do PC', 'Áudio do Windows'
        return {
            'title': title,
            'artist': artist,
            'source': source,
            'playing': True,
            'cover': b'',
            'can_next': False,
            'can_previous': False,
            'position': 0,
            'duration': 0,
            'generic': True,
            'level': peak,
            'device': device.FriendlyName or 'Saída de áudio',
        }