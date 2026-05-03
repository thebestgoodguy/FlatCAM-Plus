import http.cookiejar
import os
import socket
import urllib.parse
import urllib.request
import uuid

import serial


class SerialTransport:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.handle = None

    def open(self):
        self.handle = serial.serial_for_url(
            self.port,
            self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.08,
            write_timeout=1.0,
            xonxoff=False,
            rtscts=False
        )
        try:
            self.handle.reset_input_buffer()
        except Exception:
            pass

    def close(self):
        if self.handle:
            try:
                self.handle.close()
            except Exception:
                pass
        self.handle = None

    def description(self):
        return f"{self.port} @ {self.baudrate}"

    def send_line(self, text):
        if not self.handle:
            raise ConnectionError("Serial port is closed")
        self.handle.write((text.rstrip() + "\n").encode("utf-8", errors="ignore"))
        return []

    def send_raw(self, data):
        if not self.handle:
            raise ConnectionError("Serial port is closed")
        self.handle.write(data)
        return []

    def read_lines(self):
        if not self.handle:
            return []

        lines = []
        while self.handle and self.handle.in_waiting:
            raw = self.handle.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                lines.append(line)
        return lines


class TcpTransport:
    IAC = 255
    DO = 253
    DONT = 254
    WILL = 251
    WONT = 252

    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        self.sock = None
        self.buffer = b""

    def open(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=4.0)
        self.sock.settimeout(0.06)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    def description(self):
        return f"{self.host}:{self.port}"

    def send_line(self, text):
        if not self.sock:
            raise ConnectionError("TCP socket is closed")
        self.sock.sendall((text.rstrip() + "\n").encode("utf-8", errors="ignore"))
        return []

    def send_raw(self, data):
        if not self.sock:
            raise ConnectionError("TCP socket is closed")
        self.sock.sendall(data)
        return []

    def _strip_telnet(self, data):
        clean = bytearray()
        reply = bytearray()
        i = 0

        while i < len(data):
            byte = data[i]
            if byte == self.IAC and i + 2 < len(data):
                cmd = data[i + 1]
                opt = data[i + 2]
                if cmd == self.DO:
                    reply.extend([self.IAC, self.WONT, opt])
                elif cmd == self.WILL:
                    reply.extend([self.IAC, self.DONT, opt])
                i += 3
                continue
            clean.append(byte)
            i += 1

        if reply and self.sock:
            try:
                self.sock.sendall(bytes(reply))
            except Exception:
                pass
        return bytes(clean)

    def read_lines(self):
        if not self.sock:
            return []

        while True:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                raise ConnectionError("TCP socket closed by remote host")
            self.buffer += self._strip_telnet(chunk)

        if b"\n" not in self.buffer:
            return []

        raw_lines = self.buffer.splitlines(keepends=True)
        if raw_lines and not raw_lines[-1].endswith((b"\n", b"\r")):
            self.buffer = raw_lines.pop()
        else:
            self.buffer = b""

        lines = []
        for raw in raw_lines:
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                lines.append(line)
        return lines


class HttpTransport:
    def __init__(self, base_url, user="", password=""):
        self.base_url = self._normalize_base_url(base_url)
        self.user = user
        self.password = password
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.info_text = ""

    @staticmethod
    def _normalize_base_url(url):
        url = (url or "").strip()
        if not url:
            url = "http://fluidnc.local"
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        return url.rstrip("/")

    def open(self):
        if self.user or self.password:
            login_query = urllib.parse.urlencode({
                "USER": self.user,
                "PASSWORD": self.password,
                "SUBMIT": "yes"
            })
            self._request_text(f"/login?{login_query}")
        self.info_text = self.send_command_text("[ESP800]")

    def close(self):
        self.cookie_jar.clear()

    def description(self):
        return self.base_url

    def _url(self, path):
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _request_text(self, path, data=None, headers=None, timeout=8.0):
        req = urllib.request.Request(self._url(path), data=data, headers=headers or {})
        with self.opener.open(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")

    def send_command_text(self, text):
        upper = text.strip().upper()
        param = "commandText" if upper.startswith("[ESP") or upper.startswith("$/") else "plain"
        query = urllib.parse.urlencode({param: text})
        return self._request_text(f"/command?{query}")

    def send_line(self, text):
        return self._split_response(self.send_command_text(text))

    def send_raw(self, data):
        query = urllib.parse.quote_from_bytes(data)
        return self._split_response(self._request_text(f"/command?plain={query}"))

    def read_lines(self):
        return []

    @staticmethod
    def _split_response(response):
        lines = []
        for line in response.replace("\r", "\n").split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        return lines

    def list_files(self, endpoint, path="/", action="list", filename="all"):
        query = urllib.parse.urlencode({
            "action": action,
            "filename": filename,
            "path": path or "/"
        })
        response = self._request_text(f"{endpoint}?{query}")
        return self._json_response(response)

    def upload_files(self, endpoint, path, files):
        boundary = "----FlatCAMFluidNC" + uuid.uuid4().hex
        fields = [("path", path or "/")]
        file_fields = []

        for file_path in files:
            filename = os.path.basename(file_path)
            remote_name = (path or "/").rstrip("/") + "/" + filename
            size_arg = f"{(path or '/').rstrip('/')}/{filename}S"
            with open(file_path, "rb") as f:
                payload = f.read()
            fields.append((size_arg, str(len(payload))))
            file_fields.append(("myfiles[]", remote_name, "application/octet-stream", payload))

        response = self._multipart_post(endpoint, fields, file_fields, boundary)
        return self._json_response(response)

    def _multipart_post(self, endpoint, fields, files, boundary, timeout=60.0):
        body = bytearray()

        for name, value in fields:
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")

        for name, filename, content_type, payload in files:
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
            body.extend(payload)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("ascii"))
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._request_text(endpoint, data=bytes(body), headers=headers, timeout=timeout)

    @staticmethod
    def _json_response(response):
        import json

        try:
            return json.loads(response)
        except Exception:
            return {"status": response.strip() or "OK", "files": []}
