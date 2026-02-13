# Reydey Media File Server

**Last Updated**: 2026-02-13
**Related Systems**: Komodo (Container 128, 192.168.0.179)

## Summary
Password-protected nginx file server serving GoPro media from `/mnt/pictures/personal/alec/reydey` (78GB). Deployed as a Komodo stack with media-optimized nginx configuration for large video file streaming.

## Access
- **URL**: http://192.168.0.179:8105
- **Credentials**: settling / friends
- **Komodo Stack**: `reydey` at `/etc/komodo/stacks/reydey/`

## How It Works
- **nginx:alpine** serves a browsable directory listing (autoindex) with HTTP Basic Auth
- Volume mounted read-only from `/mnt/pictures/personal/alec/reydey`
- The `mp4` module enables video seeking/scrubbing for .mp4/.MP4 files without downloading the entire file
- Based on the same pattern as the `portrait` stack (port 8100, serves hometheater media)

## Nginx Media Optimizations
| Directive | Purpose |
|-----------|---------|
| `sendfile on` | Kernel-level zero-copy file transfer |
| `tcp_nopush` / `tcp_nodelay` | Efficient packet handling for streaming |
| `output_buffers 2 1m` | Double-buffering for large file reads |
| `keepalive_timeout 300s` | Prevents dropped connections during long streams |
| `send_timeout 300s` | Tolerates slow clients streaming large video |
| `mp4` + `mp4_buffer_size 4m` | Enables MP4 pseudo-streaming (seek by time) |
| `mp4_max_buffer_size 16m` | Handles large GoPro moov atoms |

## Resource Limits
- CPU: 1.0 (higher than portrait's 0.5 for video streaming)
- Memory: 1024M (higher than portrait's 512M for MP4 buffer overhead)
- PIDs: 50

**Note**: Do NOT enable `aio threads` with a PID limit of 50 — nginx spawns 32 threads per worker, exceeding the limit and crashing all workers.

## Compose File
Location: `/etc/komodo/stacks/reydey/compose.yaml`

```yaml
name: reydey

services:
  reydey:
    image: nginx:alpine
    container_name: reydey
    ports:
      - 8105:80
    volumes:
      - /mnt/pictures/personal/alec/reydey:/usr/share/nginx/html:ro
    command: >
      sh -c "rm -f /usr/share/nginx/html/index.html /usr/share/nginx/html/50x.html 2>/dev/null;
      echo 'settling:$$apr1$$3vnEJlNW$$2Ts1DGqhURJeGUjpRWP/4/' > /etc/nginx/.htpasswd &&
      echo 'server {
        listen 80;
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;
        output_buffers 2 1m;
        keepalive_timeout 300s;
        send_timeout 300s;
        client_max_body_size 0;
        location / {
          auth_basic \"Restricted\";
          auth_basic_user_file /etc/nginx/.htpasswd;
          root /usr/share/nginx/html;
          autoindex on;
          autoindex_exact_size off;
          autoindex_localtime on;
        }
        location ~* \.mp4$$ {
          auth_basic \"Restricted\";
          auth_basic_user_file /etc/nginx/.htpasswd;
          root /usr/share/nginx/html;
          mp4;
          mp4_buffer_size 4m;
          mp4_max_buffer_size 16m;
        }
      }' > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1024M
          pids: 50
        reservations:
          cpus: '0.1'
          memory: 128M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    security_opt:
      - no-new-privileges:true
    init: true

networks: {}
```

## Replicating for Another Directory
To create a new file server for a different directory:
1. Copy `/etc/komodo/stacks/reydey/` to a new stack name
2. Change the volume mount path, container name, port, and stack name
3. Generate a new htpasswd hash: `docker run --rm httpd:alpine htpasswd -nb username password`
4. Escape `$` as `$$` in the compose file (Docker Compose requirement)
5. Deploy via Komodo UI

## Verification
```bash
# Container running
docker ps --filter name=reydey

# Auth works
curl -u settling:friends http://192.168.0.179:8105/

# No-auth rejected
curl http://192.168.0.179:8105/  # Should return 401

# Range requests work (video seeking)
curl -u settling:friends -H "Range: bytes=0-1023" -I http://192.168.0.179:8105/GOPR9986.MP4
# Should return 206 Partial Content
```

## Troubleshooting
- **Workers crashing with `pthread_create() failed`**: PID limit too low for `aio threads`. Remove `aio threads` and `directio` directives, or increase PID limit significantly (250+).
- **401 on correct password**: Verify the htpasswd hash — regenerate with `docker run --rm httpd:alpine htpasswd -nb settling friends` and ensure `$` is escaped as `$$` in compose.
- **Can't browse directory**: Check the volume mount path exists on the host and nginx has read access.
