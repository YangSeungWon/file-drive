#!/usr/bin/env python3
"""
Simple file server with upload/delete capabilities and basic authentication
"""
import http.server
import socketserver
import os
import base64
import cgi
import urllib.parse
from urllib.parse import quote, unquote
import sys
import argparse
import getpass
import time
from datetime import datetime
import hashlib
import json

class AuthUploadHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with upload and authentication support"""
    
    auth_key = ""
    upload_dir = ""
    
    def do_AUTHHEAD(self):
        """Send authentication headers"""
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="File Server"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
    
    def authenticate(self):
        """Check authentication"""
        auth_header = self.headers.get('Authorization')
        if auth_header is None or not auth_header.startswith('Basic '):
            self.do_AUTHHEAD()
            self.wfile.write(b'401 Unauthorized')
            return False
        
        token = auth_header.split()[1]
        if token != self.auth_key:
            self.do_AUTHHEAD()
            self.wfile.write(b'401 Unauthorized')
            return False
        return True
    
    def list_directory(self, path):
        """Generate directory listing with upload form"""
        if not self.authenticate():
            return None
        
        try:
            file_list = os.listdir(path)
        except OSError:
            self.send_error(404, "Directory not found")
            return None
        
        # Send response headers
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Generate HTML
        html = self.generate_html(path, file_list)
        self.wfile.write(html.encode('utf-8'))
        return None
    
    def generate_html(self, path, file_list):
        """Generate the HTML page"""
        # Separate directories and files
        dirs = []
        files = []
        for name in sorted(file_list):
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                dirs.append(name)
            else:
                files.append(name)
        
        # Build file items HTML
        items_html = ""
        
        # Add directories first
        for name in dirs:
            url = quote(name)
            items_html += f'''
                <li class="file-item dir">
                    <span class="file-icon" onclick="location.href='{url}'">📁</span>
                    <div class="file-info" onclick="location.href='{url}'">
                        <a href="{url}" class="file-link" onclick="event.stopPropagation()">{name}/</a>
                    </div>
                </li>
            '''
        
        # Add files
        for name in files:
            url = quote(name)
            full_path = os.path.join(path, name)
            size = os.path.getsize(full_path)
            size_str = self.format_size(size)
            icon = self.get_file_icon(name)
            
            # Get file modification time and hash
            mtime = os.path.getmtime(full_path)
            time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            
            # Calculate file hash (first 16 chars of SHA256)
            with open(full_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            
            items_html += f'''
                <li class="file-item" data-hash="{file_hash}">
                    <span class="file-icon" onclick="location.href='{url}'">{icon}</span>
                    <div class="file-info" onclick="location.href='{url}'">
                        <a href="{url}" class="file-link" onclick="event.stopPropagation()">{name}</a>
                        <div class="file-meta">
                            <span class="file-size">{size_str}</span>
                            <span class="file-time">{time_str}</span>
                            <span class="file-hash" title="해시: {file_hash}">🔒 {file_hash[:8]}...</span>
                        </div>
                    </div>
                    <button class="delete-btn" onclick="deleteFile('{name}')">삭제</button>
                </li>
            '''
        
        if not dirs and not files:
            items_html = '<div class="empty">No files uploaded yet</div>'
        
        return f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Server</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 10px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }}
        h1 {{ font-size: 20px; color: #333; }}
        
        .upload-section {{ padding: 16px; background: #fafafa; border-bottom: 1px solid #e0e0e0; }}
        .upload-zone {{ border: 2px dashed #4CAF50; border-radius: 8px; padding: 24px; text-align: center; background: white; transition: all 0.3s; cursor: pointer; }}
        .upload-zone.dragover {{ background: #e8f5e9; border-color: #2e7d32; }}
        .upload-zone:hover {{ background: #f1f8f4; }}
        .file-input-label {{ display: block; cursor: pointer; }}
        .file-input-label .icon {{ font-size: 48px; margin-bottom: 12px; }}
        .file-input-label .text {{ color: #666; font-size: 14px; }}
        .file-input-label .sub {{ color: #999; font-size: 12px; margin-top: 4px; }}
        input[type="file"] {{ display: none; }}
        
        .selected-file {{ margin-top: 12px; padding: 12px; background: #e8f5e9; border-radius: 4px; display: none; align-items: center; gap: 10px; }}
        .selected-file.show {{ display: flex; }}
        .selected-file-name {{ flex: 1; font-size: 14px; color: #2e7d32; word-break: break-all; }}
        .upload-btn {{ padding: 8px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; }}
        .upload-btn:active {{ transform: scale(0.98); }}
        .cancel-btn {{ padding: 8px 16px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }}
        
        .files-section {{ padding: 12px; }}
        .file-list {{ list-style: none; }}
        .file-item {{ display: flex; align-items: center; padding: 12px; border-radius: 6px; margin-bottom: 4px; transition: background 0.2s; cursor: pointer; }}
        .file-item:active {{ background: #e0e0e0; }}
        .file-item:hover {{ background: #f5f5f5; }}
        .file-icon {{ margin-right: 12px; font-size: 24px; min-width: 24px; }}
        .file-info {{ flex: 1; min-width: 0; }}
        .file-link {{ text-decoration: none; color: #333; display: block; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .file-meta {{ display: flex; gap: 12px; margin-top: 2px; flex-wrap: wrap; }}
        .file-size {{ color: #888; font-size: 12px; }}
        .file-time {{ color: #999; font-size: 12px; }}
        .file-hash {{ color: #6a9fb5; font-size: 11px; font-family: monospace; cursor: help; }}
        .uploading-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center; z-index: 1000; }}
        .uploading-overlay.show {{ display: flex; }}
        .uploading-box {{ background: white; padding: 30px; border-radius: 8px; text-align: center; }}
        .spinner {{ border: 3px solid #f3f3f3; border-top: 3px solid #4CAF50; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .delete-btn {{ padding: 4px 8px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-left: 8px; opacity: 0.9; }}
        .delete-btn:hover {{ opacity: 1; }}
        .delete-btn:active {{ transform: scale(0.95); }}
        .dir .file-link {{ color: #2196F3; font-weight: 500; }}
        .empty {{ text-align: center; padding: 40px; color: #999; }}
        
        @media (max-width: 600px) {{
            body {{ padding: 0; background: white; }}
            .container {{ border-radius: 0; box-shadow: none; }}
            .header {{ padding: 14px 16px; position: sticky; top: 0; background: white; z-index: 10; }}
            h1 {{ font-size: 18px; }}
            .upload-section {{ padding: 12px; }}
            .file-item {{ padding: 14px 12px; }}
            .file-icon {{ font-size: 20px; }}
        }}
        
        @media (min-width: 601px) {{
            .upload-zone {{ padding: 32px; }}
            .file-input-label .icon {{ font-size: 64px; }}
            .file-input-label .text {{ font-size: 16px; }}
        }}
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
                {items_html}
            </ul>
        </div>
    </div>
    <script>
        function dragOverHandler(ev) {{
            ev.preventDefault();
            ev.currentTarget.classList.add('dragover');
        }}
        function dragLeaveHandler(ev) {{
            ev.currentTarget.classList.remove('dragover');
        }}
        function dropHandler(ev) {{
            ev.preventDefault();
            ev.currentTarget.classList.remove('dragover');
            const files = ev.dataTransfer.files;
            if (files.length > 0) {{
                document.getElementById('fileInput').files = files;
                fileSelected(document.getElementById('fileInput'));
            }}
        }}
        function fileSelected(input) {{
            if (input.files.length > 0) {{
                const file = input.files[0];
                document.getElementById('fileName').textContent = file.name;
                document.getElementById('selectedFile').classList.add('show');
            }}
        }}
        function cancelFile() {{
            document.getElementById('fileInput').value = '';
            document.getElementById('selectedFile').classList.remove('show');
        }}
        
        // 자동 업로드 (선택 즉시)
        document.getElementById('fileInput').addEventListener('change', function() {{
            if (this.files.length > 0) {{
                uploadFile();
            }}
        }});
        
        async function uploadFile() {{
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            // 파일 해시 계산
            const fileHash = await calculateFileHash(file);
            
            // 서버의 파일 해시 목록 가져오기
            const response = await fetch('/api/files');
            const serverFiles = await response.json();
            
            // 같은 이름의 파일이 있는지 확인
            if (serverFiles[file.name]) {{
                if (serverFiles[file.name] === fileHash.substring(0, 16)) {{
                    if (confirm(`"⚠️ ${{file.name}}"은(는) 이미 동일한 파일이 존재합니다 (해시: ${{fileHash.substring(0, 8)}}...).\n\n그래도 업로드하시겠습니까?`)) {{
                        submitUploadForm();
                    }} else {{
                        cancelFile();
                        return;
                    }}
                }} else {{
                    // 다른 해시면 파일명에 postfix 추가
                    const nameParts = file.name.split('.');
                    const ext = nameParts.length > 1 ? '.' + nameParts.pop() : '';
                    const baseName = nameParts.join('.');
                    const timestamp = new Date().getTime();
                    const newName = `${{baseName}}_${{timestamp}}${{ext}}`;
                    
                    // 파일 이름 변경을 위해 새 File 객체 생성
                    const newFile = new File([file], newName, {{ type: file.type }});
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(newFile);
                    fileInput.files = dataTransfer.files;
                    
                    alert(`파일명이 같지만 내용이 다른 파일이 있어 "${{newName}}"으로 저장합니다.`);
                    submitUploadForm();
                }}
            }} else {{
                submitUploadForm();
            }}
        }}
        
        function submitUploadForm() {{
            // 로딩 오버레이 추가
            const overlay = document.createElement('div');
            overlay.className = 'uploading-overlay show';
            overlay.innerHTML = `
                <div class="uploading-box">
                    <div class="spinner"></div>
                    <div>파일 업로드 중...</div>
                </div>
            `;
            document.body.appendChild(overlay);
            
            // 폼 제출
            setTimeout(() => {{
                document.getElementById('uploadForm').submit();
            }}, 100);
        }}
        
        async function calculateFileHash(file) {{
            const buffer = await file.arrayBuffer();
            const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            return hashHex;
        }}
        
        // 파일 삭제 함수
        function deleteFile(filename) {{
            if (confirm('"' + filename + '" 파일을 삭제하시겠습니까?')) {{
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/?delete=' + encodeURIComponent(filename);
                document.body.appendChild(form);
                form.submit();
            }}
        }}
    </script>
    <div class="uploading-overlay" id="uploadingOverlay">
        <div class="uploading-box">
            <div class="spinner"></div>
            <div>파일 업로드 중...</div>
        </div>
    </div>
</body>
</html>'''
    
    def format_size(self, size):
        """Format file size in human-readable format"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/(1024*1024):.1f} MB"
    
    def get_file_icon(self, filename):
        """Get appropriate icon for file type"""
        name_lower = filename.lower()
        if name_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg')):
            return '🖼️'
        elif name_lower.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            return '🎬'
        elif name_lower.endswith('.pdf'):
            return '📄'
        elif name_lower.endswith(('.ppt', '.pptx')):
            return '📊'
        elif name_lower.endswith(('.doc', '.docx')):
            return '📝'
        elif name_lower.endswith(('.zip', '.tar', '.gz', '.rar')):
            return '🗜️'
        else:
            return '📎'
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            return self.list_directory(os.getcwd())
        elif self.path == '/api/files':
            return self.get_file_hashes()
        else:
            if not self.authenticate():
                return
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def get_file_hashes(self):
        """Return JSON with file hashes"""
        if not self.authenticate():
            return
        
        file_hashes = {}
        for filename in os.listdir(os.getcwd()):
            if os.path.isfile(filename):
                with open(filename, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
                    file_hashes[filename] = file_hash
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(file_hashes).encode())
    
    def do_POST(self):
        """Handle POST requests (upload and delete)"""
        if not self.authenticate():
            return
        
        # Handle delete request
        if '?delete=' in self.path:
            filename = unquote(self.path.split('?delete=')[1])
            filepath = os.path.join(os.getcwd(), filename)
            if os.path.exists(filepath) and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                    print(f"Deleted file: {filename}")
                except Exception as e:
                    self.send_error(500, f"Error deleting file: {e}")
                    return
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        
        # Handle file upload
        ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
        if ctype != 'multipart/form-data':
            self.send_error(400, "Bad request: not multipart/form-data")
            return
        
        pdict['boundary'] = pdict['boundary'].encode('utf-8')
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST'},
            keep_blank_values=True
        )
        
        if 'file' not in form:
            self.send_error(400, "No file field in form.")
            return
        
        field = form['file']
        if not field.filename:
            self.send_error(400, "Empty filename.")
            return
        
        filename = os.path.basename(field.filename)
        filepath = os.path.join(os.getcwd(), filename)
        
        with open(filepath, 'wb') as f:
            f.write(field.file.read())
        
        print(f"Uploaded file: {filename}")
        
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Simple file server with upload/delete capabilities')
    parser.add_argument('-p', '--port', type=int, default=7113, help='Port to serve on (default: 7113)')
    parser.add_argument('-d', '--directory', default='./uploads', help='Directory to serve (default: ./uploads)')
    parser.add_argument('-u', '--user', default='admin', help='Username for authentication (default: admin)')
    parser.add_argument('--password', help='Password for authentication (will prompt if not provided)')
    
    args = parser.parse_args()
    
    # Get password
    if args.password:
        password = args.password
    else:
        password = getpass.getpass(f"Password for user '{args.user}': ")
    
    # Ensure directory exists
    if not os.path.exists(args.directory):
        os.makedirs(args.directory)
    
    # Change to serving directory
    os.chdir(args.directory)
    
    # Set up authentication
    auth_string = f"{args.user}:{password}"
    AuthUploadHandler.auth_key = base64.b64encode(auth_string.encode()).decode()
    AuthUploadHandler.upload_dir = args.directory
    
    # Start server with SO_REUSEADDR option
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), AuthUploadHandler) as httpd:
        print(f"Serving HTTP on 0.0.0.0 port {args.port} (dir: {os.getcwd()})...")
        print(f"Access at: http://localhost:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
        finally:
            httpd.server_close()


if __name__ == '__main__':
    main()