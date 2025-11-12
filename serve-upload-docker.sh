#!/usr/bin/env bash
# serve_upload_docker.sh — Docker-optimized file server with upload + Basic Auth
# Reads configuration from environment variables

# Use environment variables or defaults
PORT=${PORT:-7113}
DIR=${UPLOAD_DIR:-/app/uploads}
USER=${SERVER_USER:-admin}
PASS=${SERVER_PASSWORD:-password}

# 1) Directory check
if [[ ! -d "$DIR" ]]; then
  echo "Error: Directory '$DIR' does not exist. Creating it..."
  mkdir -p "$DIR"
fi

echo "Starting file server..."
echo "  Directory: $DIR"
echo "  User: $USER"
echo "  Port: $PORT"

# 2) Create temporary Python server script
TMP_SCRIPT=$(mktemp /tmp/serve_upload.XXXXXX.py)
cat > "$TMP_SCRIPT" << 'PYTHON'
import http.server, socketserver, os, base64, cgi
from urllib.parse import quote
import sys

class AuthUploadHandler(http.server.SimpleHTTPRequestHandler):
    auth_key = ""
    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Upload"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def authenticate(self):
        hdr = self.headers.get('Authorization')
        if hdr is None or not hdr.startswith('Basic '):
            self.do_AUTHHEAD()
            self.wfile.write(b'401 Unauthorized')
            return False
        token = hdr.split()[1]
        if token != self.auth_key:
            self.do_AUTHHEAD()
            self.wfile.write(b'401 Unauthorized')
            return False
        return True

    def list_directory(self, path):
        if not self.authenticate():
            return None
        files = os.listdir(path)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Server</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 10px; }
        .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header { padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }
        h1 { font-size: 20px; color: #333; }

        .upload-section { padding: 16px; background: #fafafa; border-bottom: 1px solid #e0e0e0; }
        .upload-zone { border: 2px dashed #4CAF50; border-radius: 8px; padding: 24px; text-align: center; background: white; transition: all 0.3s; cursor: pointer; }
        .upload-zone.dragover { background: #e8f5e9; border-color: #2e7d32; }
        .upload-zone:hover { background: #f1f8f4; }
        .file-input-label { display: block; cursor: pointer; }
        .file-input-label .icon { font-size: 48px; margin-bottom: 12px; }
        .file-input-label .text { color: #666; font-size: 14px; }
        .file-input-label .sub { color: #999; font-size: 12px; margin-top: 4px; }
        input[type="file"] { display: none; }

        .selected-file { margin-top: 12px; padding: 12px; background: #e8f5e9; border-radius: 4px; display: none; align-items: center; gap: 10px; }
        .selected-file.show { display: flex; }
        .selected-file-name { flex: 1; font-size: 14px; color: #2e7d32; word-break: break-all; }
        .upload-btn { padding: 8px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; }
        .upload-btn:active { transform: scale(0.98); }
        .cancel-btn { padding: 8px 16px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }

        .files-section { padding: 12px; }
        .file-list { list-style: none; }
        .file-item { display: flex; align-items: center; padding: 12px; border-radius: 6px; margin-bottom: 4px; transition: background 0.2s; cursor: pointer; }
        .file-item:active { background: #e0e0e0; }
        .file-item:hover { background: #f5f5f5; }
        .file-icon { margin-right: 12px; font-size: 24px; min-width: 24px; }
        .file-info { flex: 1; min-width: 0; }
        .file-link { text-decoration: none; color: #333; display: block; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .file-size { color: #888; font-size: 12px; margin-top: 2px; }
        .delete-btn { padding: 4px 8px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-left: 8px; opacity: 0.9; }
        .delete-btn:hover { opacity: 1; }
        .delete-btn:active { transform: scale(0.95); }
        .dir .file-link { color: #2196F3; font-weight: 500; }
        .empty { text-align: center; padding: 40px; color: #999; }

        @media (max-width: 600px) {
            body { padding: 0; background: white; }
            .container { border-radius: 0; box-shadow: none; }
            .header { padding: 14px 16px; position: sticky; top: 0; background: white; z-index: 10; }
            h1 { font-size: 18px; }
            .upload-section { padding: 12px; }
            .file-item { padding: 14px 12px; }
            .file-icon { font-size: 20px; }
        }

        @media (min-width: 601px) {
            .upload-zone { padding: 32px; }
            .file-input-label .icon { font-size: 64px; }
            .file-input-label .text { font-size: 16px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁 File Server</h1>
        </div>
        <div class="upload-section">
            <form enctype="multipart/form-data" method="post" id="uploadForm">
                <div class="upload-zone" onclick="document.getElementById('fileInput').click()" ondrop="dropHandler(event);" ondragover="dragOverHandler(event);" ondragleave="dragLeaveHandler(event);">
                    <label class="file-input-label">
                        <div class="icon">📤</div>
                        <div class="text">클릭하거나 파일을 드래그하세요</div>
                        <div class="sub">모든 파일 형식 지원</div>
                        <input type="file" name="file" id="fileInput" onchange="fileSelected(this)" multiple>
                    </label>
                </div>
                <div class="selected-file" id="selectedFile">
                    <span class="selected-file-name" id="fileName"></span>
                    <button type="button" class="cancel-btn" onclick="cancelFile()">취소</button>
                    <button type="submit" class="upload-btn">업로드</button>
                </div>
            </form>
        </div>
        <div class="files-section">
            <ul class="file-list">
'''
        self.wfile.write(html.encode())

        # Separate files and directories
        dirs = []
        files_list = []
        for name in sorted(files):
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                dirs.append(name)
            else:
                files_list.append(name)

        # Display directories first
        for name in dirs:
            url = quote(name)
            self.wfile.write(f'''
                <li class="file-item dir" onclick="location.href='{url}'">
                    <span class="file-icon">📁</span>
                    <div class="file-info">
                        <a href="{url}" class="file-link" onclick="event.stopPropagation()">{name}/</a>
                    </div>
                </li>
            '''.encode())

        # Display files
        for name in files_list:
            url = quote(name)
            size = os.path.getsize(os.path.join(path, name))
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024*1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/(1024*1024):.1f} MB"

            # Icons based on file extension
            if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg')):
                icon = '🖼️'
            elif name.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                icon = '🎬'
            elif name.endswith(('.pdf')):
                icon = '📄'
            elif name.endswith(('.ppt', '.pptx')):
                icon = '📊'
            elif name.endswith(('.doc', '.docx')):
                icon = '📝'
            elif name.endswith(('.zip', '.tar', '.gz', '.rar')):
                icon = '🗜️'
            else:
                icon = '📎'

            self.wfile.write(f'''
                <li class="file-item">
                    <span class="file-icon" onclick="location.href='{url}'">{icon}</span>
                    <div class="file-info" onclick="location.href='{url}'">
                        <a href="{url}" class="file-link" onclick="event.stopPropagation()">{name}</a>
                        <span class="file-size">{size_str}</span>
                    </div>
                    <button class="delete-btn" onclick="deleteFile('{name}')">삭제</button>
                </li>
            '''.encode())

        if not dirs and not files_list:
            self.wfile.write(b'<div class="empty">No files uploaded yet</div>')

        self.wfile.write('''
            </ul>
        </div>
    </div>
    <script>
        function dragOverHandler(ev) {
            ev.preventDefault();
            ev.currentTarget.classList.add('dragover');
        }
        function dragLeaveHandler(ev) {
            ev.currentTarget.classList.remove('dragover');
        }
        function dropHandler(ev) {
            ev.preventDefault();
            ev.currentTarget.classList.remove('dragover');
            const files = ev.dataTransfer.files;
            if (files.length > 0) {
                document.getElementById('fileInput').files = files;
                fileSelected(document.getElementById('fileInput'));
            }
        }
        function fileSelected(input) {
            if (input.files.length > 0) {
                const file = input.files[0];
                document.getElementById('fileName').textContent = file.name;
                document.getElementById('selectedFile').classList.add('show');
            }
        }
        function cancelFile() {
            document.getElementById('fileInput').value = '';
            document.getElementById('selectedFile').classList.remove('show');
        }

        // Auto upload (immediately on selection)
        document.getElementById('fileInput').addEventListener('change', function() {
            if (this.files.length > 0) {
                setTimeout(() => {
                    document.getElementById('uploadForm').submit();
                }, 100);
            }
        });

        // File delete function
        function deleteFile(filename) {
            if (confirm('"' + filename + '" 파일을 삭제하시겠습니까?')) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/?delete=' + encodeURIComponent(filename);
                document.body.appendChild(form);
                form.submit();
            }
        }
    </script>
</body>
</html>'''.encode())
        return None

    def do_GET(self):
        if self.path == '/':
            return self.list_directory(os.getcwd())
        else:
            if not self.authenticate(): return
            return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if not self.authenticate(): return

        # Handle delete request
        if '?delete=' in self.path:
            import urllib.parse
            filename = urllib.parse.unquote(self.path.split('?delete=')[1])
            filepath = os.path.join(os.getcwd(), filename)
            if os.path.exists(filepath) and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    self.send_error(500, f"Error deleting file: {e}")
                    return
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return

        # Handle upload
        ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
        if ctype != 'multipart/form-data':
            self.send_error(400, "Bad request: not multipart/form-data")
            return
        pdict['boundary'] = pdict['boundary'].encode('utf-8')
        form = cgi.FieldStorage(fp=self.rfile,
                                headers=self.headers,
                                environ={'REQUEST_METHOD':'POST'},
                                keep_blank_values=True)
        if 'file' not in form:
            self.send_error(400, "No file field in form.")
            return
        field = form['file']
        if not field.filename:
            self.send_error(400, "Empty filename.")
            return
        filename = os.path.basename(field.filename)
        outpath = os.path.join(os.getcwd(), filename)
        with open(outpath, 'wb') as out:
            out.write(field.file.read())
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

if __name__ == '__main__':
    # Arguments from environment: user, pwd, directory, port
    user, pwd, directory, port = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    key = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    AuthUploadHandler.auth_key = key
    os.chdir(directory)
    with socketserver.TCPServer(("", port), AuthUploadHandler) as httpd:
        print(f"Serving HTTP on 0.0.0.0 port {port} (dir: {directory}) …")
        httpd.serve_forever()
PYTHON

# 3) Execute the server
chmod +x "$TMP_SCRIPT"
python3 "$TMP_SCRIPT" "$USER" "$PASS" "$DIR" "$PORT"
trap 'rm -f "$TMP_SCRIPT"' EXIT
