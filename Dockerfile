FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the server script
COPY serve-upload-docker.sh /app/serve-upload-docker.sh

# Make script executable
RUN chmod +x /app/serve-upload-docker.sh

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose the default port
EXPOSE 7113

# Set environment variables with defaults
ENV SERVER_USER=admin
ENV SERVER_PASSWORD=password
ENV PORT=7113
ENV UPLOAD_DIR=/app/uploads

# Run the server
CMD ["/app/serve-upload-docker.sh"]
