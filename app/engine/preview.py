from __future__ import annotations

import queue
import threading
import time
from multiprocessing.shared_memory import SharedMemory


class BytesPipe:
    def __init__(self) -> None:
        self._q: queue.Queue[bytes] = queue.Queue(maxsize=256)
        self._eof = threading.Event()

    def write(self, data: bytes) -> None:
        if not self._eof.is_set():
            try:
                self._q.put_nowait(data)
            except queue.Full:
                pass

    def read(self, size: int) -> bytes | None:
        while not self._eof.is_set():
            try:
                return self._q.get(timeout=0.5)
            except queue.Empty:
                continue
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return b""

    def close(self) -> None:
        self._eof.set()


class PreviewThread(threading.Thread):
    def __init__(self, pipe: BytesPipe, shm_name: str, size: tuple[int, int],
                 fps: int, notify: callable) -> None:
        super().__init__(name="preview", daemon=True)
        self.pipe = pipe
        self.shm_name = shm_name
        self.size = size
        self.fps = fps
        self.notify = notify
        self._stop_event = threading.Event()
        self._idx = 0

    def stop(self) -> None:
        self._stop_event.set()
        self.pipe.close()

    def run(self) -> None:
        import av
        import logging

        log = logging.getLogger("engine")
        w, h = self.size
        frame_bytes = w * h * 3
        shm = SharedMemory(name=self.shm_name)
        try:
            period = 1.0 / max(1, self.fps)
            last = 0.0
            while not self._stop_event.is_set():
                try:
                    container = av.open(self.pipe, mode="r")
                    video = next((s for s in container.streams if s.type == "video"), None)
                    if video is None:
                        time.sleep(0.5)
                        continue
                    video.thread_type = "AUTO"
                    for frame in container.decode(video):
                        if self._stop_event.is_set():
                            break
                        now = time.monotonic()
                        if now - last < period:
                            continue
                        last = now
                        try:
                            rgb = frame.reformat(width=w, height=h, format="rgb24")
                            arr = rgb.to_ndarray()
                            off = (self._idx % 2) * frame_bytes
                            shm.buf[off : off + frame_bytes] = arr.tobytes()
                            self._idx += 1
                            self.notify(self._idx % 2, w, h)
                        except Exception:
                            continue
                except Exception as exc:
                    log.warning("preview decode restart: %s", exc)
                    time.sleep(0.2)
        finally:
            try:
                shm.close()
            except Exception:
                pass
