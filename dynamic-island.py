"""Ilha Dinâmica minimalista para Windows 10/11 (PySide6 + PyWinRT).

Spotify e YouTube via sessões de mídia do próprio Windows (SMTC).
Monitoramento opcional: NVIDIA NVML e LibreHardwareMonitor (WMI).
"""

import asyncio
import queue
import sys
import threading
import time

# O monitor de áudio roda em uma thread sem loop de mensagens; COM deve usar MTA.
sys.coinit_flags = 0

import psutil
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QLinearGradient, QRadialGradient, QPen
from PySide6.QtWidgets import QApplication, QWidget

from island_view import Island


class MediaWorker(QThread):
    changed = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.stop_signal = threading.Event()
        self.commands = queue.Queue()

    def control(self, command):
        self.commands.put(command)

    def stop(self):
        self.stop_signal.set()

    async def _get_thumbnail(self, thumb):
        if not thumb:
            return b''
        try:
            from winrt.windows.storage.streams import InputStreamOptions
            stream = await thumb.open_read_async()
            try:
                size = min(int(stream.size), 3_000_000)
                if size <= 0:
                    return b''
                buffer = bytearray(size)
                data = await stream.read_async(buffer, size, InputStreamOptions.NONE)
                return bytes(data)
            finally:
                if hasattr(stream, 'close'):
                    stream.close()
        except Exception:
            return b''

    async def loop(self):
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
            )
        except ImportError:
            MediaManager = PlaybackStatus = None
            self.error.emit('Metadados de mídia indisponíveis: instale winrt-Windows.Media.Control.')

        try:
            from audio_sources import AudioActivityProbe
            probe = AudioActivityProbe()
        except ImportError:
            probe = None
            self.error.emit('Detecção de áudio indisponível: instale pycaw.')

        manager = None
        next_manager_attempt = 0
        last_media_key = None
        last_cover = b''
        last_audio = None
        last_heard = 0
        while not self.stop_signal.is_set():
            now = time.monotonic()
            if MediaManager and manager is None and now >= next_manager_attempt:
                try:
                    manager = await MediaManager.request_async()
                except Exception as exc:
                    self.error.emit(f'Sessões de mídia do Windows indisponíveis: {exc}')
                    next_manager_attempt = now + 30

            audio_data = None
            if probe:
                try:
                    audio_data = probe.snapshot()
                    if audio_data:
                        last_audio = audio_data
                        last_heard = now
                except Exception as exc:
                    self.error.emit(f'Falha ao detectar áudio: {exc}')
            if not audio_data and last_audio and now - last_heard < 2.5:
                audio_data = last_audio

            active = None
            media_data = None
            try:
                if manager:
                    sessions = list(manager.get_sessions() or [])
                    current = manager.get_current_session()

                    def is_playing(session):
                        try:
                            info = session.get_playback_info()
                            return bool(info and info.playback_status == PlaybackStatus.PLAYING)
                        except Exception:
                            return False

                    # Preferir uma sessão tocando; depois a sessão corrente pausada.
                    active = current if current and is_playing(current) else next(
                        (s for s in sessions if is_playing(s)), current
                    )

                while True:
                    try:
                        action = self.commands.get_nowait()
                    except queue.Empty:
                        break
                    if active:
                        try:
                            if action == 'toggle':
                                await active.try_toggle_play_pause_async()
                            elif action == 'next':
                                await active.try_skip_next_async()
                            elif action == 'previous':
                                await active.try_skip_previous_async()
                        except Exception as exc:
                            self.error.emit(f'Controle de mídia indisponível: {exc}')

                if active:
                    props = await active.try_get_media_properties_async()
                    info = active.get_playback_info()
                    try:
                        timeline = active.get_timeline_properties()
                        position = max(0, int(timeline.position.total_seconds())) if timeline else 0
                        duration = max(0, int((timeline.end_time - timeline.start_time).total_seconds())) if timeline else 0
                    except Exception:
                        position = duration = 0
                    playing = is_playing(active)
                    source_id = active.source_app_user_model_id or ''
                    title = str(props.title or 'Sem título') if props else 'Sem título'
                    artist = str(props.artist or props.subtitle or '') if props else ''
                    key = (source_id, title, artist)
                    if key != last_media_key:
                        last_cover = await self._get_thumbnail(props.thumbnail if props else None)
                        last_media_key = key
                    media_data = {
                        'title': title,
                        'artist': artist,
                        'source': source_id,
                        'playing': playing,
                        'cover': last_cover,
                        'can_next': bool(info and info.controls and info.controls.is_next_enabled),
                        'can_previous': bool(info and info.controls and info.controls.is_previous_enabled),
                        'position': position,
                        'duration': duration,
                        'generic': False,
                    }
            except Exception as exc:
                self.error.emit(f'Falha ao consultar mídia: {exc}')
                manager = None
                next_manager_attempt = time.monotonic() + 30
            if media_data and media_data['playing']:
                self.changed.emit(media_data)
            elif audio_data:
                self.changed.emit(audio_data)
            else:
                self.changed.emit(media_data)
            await asyncio.sleep(0.9)

    def run(self):
        com = None
        try:
            import comtypes
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
            com = comtypes
        except ImportError:
            pass
        try:
            asyncio.run(self.loop())
        finally:
            if com:
                com.CoUninitialize()


class MetricsWorker(QThread):
    changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.stop_signal = threading.Event()

    def stop(self):
        self.stop_signal.set()

    def run(self):
        # NVML fornece GPU NVIDIA; em outras GPUs usamos sensores do LibreHardwareMonitor.
        nvml = None
        gpu_handle = None
        try:
            import pynvml
            pynvml.nvmlInit()
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            nvml = pynvml
        except Exception:
            nvml = None

        hwmon = None
        com = None
        try:
            import pythoncom
            import wmi
            pythoncom.CoInitialize()
            com = pythoncom
            try:
                hwmon = wmi.WMI(namespace=r'root\LibreHardwareMonitor')
            except Exception:
                hwmon = None
        except Exception:
            hwmon = None

        psutil.cpu_percent(interval=None)
        try:
            while not self.stop_signal.is_set():
                data = {
                    'CPU': f'{psutil.cpu_percent(interval=None):.0f}%',
                    'RAM': f'{psutil.virtual_memory().percent:.0f}%',
                    'GPU': '—',
                    'CPU Temp': '—',
                    'GPU Temp': '—',
                }
                if nvml and gpu_handle:
                    try:
                        usage = nvml.nvmlDeviceGetUtilizationRates(gpu_handle)
                        data['GPU'] = f'{usage.gpu:.0f}%'
                        temp = nvml.nvmlDeviceGetTemperature(
                            gpu_handle, nvml.NVML_TEMPERATURE_GPU
                        )
                        data['GPU Temp'] = f'{temp:.0f}°C'
                    except Exception:
                        pass
                if hwmon:
                    try:
                        for s in hwmon.Sensor():
                            typ = str(s.SensorType or '').lower()
                            name = str(s.Name or '').lower()
                            identity = str(s.Identifier or '').lower()
                            value = float(s.Value)
                            if typ == 'temperature':
                                if 'cpu' in identity and (
                                    'package' in name or data['CPU Temp'] == '—'
                                ):
                                    data['CPU Temp'] = f'{value:.0f}°C'
                                if 'gpu' in identity and (
                                    'core' in name or data['GPU Temp'] == '—'
                                ):
                                    data['GPU Temp'] = f'{value:.0f}°C'
                            elif typ == 'load' and 'gpu' in identity and (
                                'core' in name or data['GPU'] == '—'
                            ):
                                data['GPU'] = f'{value:.0f}%'
                    except Exception:
                        hwmon = None
                self.changed.emit(data)
                self.stop_signal.wait(2.5)
        finally:
            if nvml:
                try:
                    nvml.nvmlShutdown()
                except Exception:
                    pass
            if com:
                com.CoUninitialize()


class AlbumArt(QWidget):
    def __init__(self, size=72):
        super().__init__()
        self.setFixedSize(size, size)
        self.pixmap = None
        self.accent_color = QColor('#6bbcff')
        self.base_color = QColor('#0b1423')

    def set_data(self, data):
        pix = QPixmap()
        self.pixmap = pix if data and pix.loadFromData(data) else None
        self.update()

    def set_theme_colors(self, accent, base):
        self.accent_color = QColor(accent)
        self.base_color = QColor(base)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        radius = 11 if self.width() > 40 else 7
        path.addRoundedRect(self.rect(), radius, radius)
        painter.setClipPath(path)
        if self.pixmap and not self.pixmap.isNull():
            pix = self.pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - pix.width()) // 2
            y = (self.height() - pix.height()) // 2
            painter.drawPixmap(x, y, pix)
        else:
            top_color = self.accent_color.darker(220)
            bottom_color = self.base_color.darker(130)
            base = QLinearGradient(0, 0, self.width(), self.height())
            base.setColorAt(0, top_color)
            base.setColorAt(1, bottom_color)
            painter.fillPath(path, base)

            glow_center = QColor(self.accent_color.lighter(135))
            glow_center.setAlpha(185)
            glow_edge = QColor(self.accent_color)
            glow_edge.setAlpha(0)
            glow = QRadialGradient(self.width() * .67, self.height() * .38, self.width() * .52)
            glow.setColorAt(0, glow_center)
            glow.setColorAt(1, glow_edge)
            painter.fillPath(path, glow)

            line_color = QColor(self.accent_color)
            line_color.setAlpha(140)
            painter.setPen(QPen(line_color, max(1, self.width() // 80)))
            for line in range(5):
                y = int(self.height() * (.68 + line * .065))
                painter.drawLine(0, y, self.width(), y)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    island = Island(MediaWorker, MetricsWorker, AlbumArt)
    island.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()