# Docker File Server

A simple, secure file server with upload capabilities, now fully dockerized.

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone and configure:**
   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env with your credentials
   nano .env
   ```

2. **Start the server:**
   ```bash
   docker-compose up -d
   ```

3. **Access the server:**
   Open your browser to `http://localhost:7113` and login with your credentials.

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

5. **Stop the server:**
   ```bash
   docker-compose down
   ```

### Using Docker CLI

**Build the image:**
```bash
docker build -t file-drive-server .
```

**Run the container:**
```bash
docker run -d \
  -p 7113:7113 \
  -e USER=admin \
  -e PASSWORD=yourpassword \
  -v $(pwd)/uploads:/app/uploads \
  --name file-server \
  file-drive-server
```

**Stop the container:**
```bash
docker stop file-server
docker rm file-server
```

## Configuration

Configure via environment variables in `.env` file or docker-compose.yml:

| Variable | Description | Default |
|----------|-------------|---------|
| `USER` | Username for Basic Auth | `admin` |
| `PASSWORD` | Password for Basic Auth | `password` |
| `PORT` | Server port (host side) | `7113` |

## Features

- Basic Authentication for security
- Drag-and-drop file upload
- File deletion capability
- Responsive mobile-friendly UI
- Persistent file storage via Docker volumes
- File type icons (images, videos, PDFs, etc.)

## Security Notes

- Always change the default password in production
- The server uses Basic Auth over HTTP - consider using HTTPS in production
- Files are stored in the `./uploads` directory and persist across container restarts

## Troubleshooting

**Port already in use:**
```bash
# Change the host port in .env or docker-compose.yml
PORT=8080
```

**Permission issues:**
```bash
# Ensure the uploads directory has proper permissions
chmod -R 755 uploads
```

**View container logs:**
```bash
docker-compose logs -f file-server
```

## Development

To modify the server:

1. Edit `serve-upload-docker.sh`
2. Rebuild the image: `docker-compose build`
3. Restart: `docker-compose up -d`

## Original Script

The original non-Docker version is available as `serve-upload.sh` which prompts for password interactively.
