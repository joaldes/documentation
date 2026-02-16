# Reyday Media File Server

**Last Updated**: 2026-02-16
**Related Systems**: Komodo (Container 128, 192.168.0.179)

## Summary
Password-protected nginx file server serving GoPro media from `/mnt/pictures/personal/alec/reyday` (142GB). Supports browsing, downloading, MP4 video streaming, and **file upload** via WebDAV PUT with a drag-and-drop browser UI. Deployed as a Komodo stack with media-optimized nginx configuration.

## Access
- **External URL**: https://reyday.1701.me
- **Internal URL**: http://192.168.0.179:8105
- **Credentials**: settling / friends
- **Upload page**: https://reyday.1701.me/upload
- **Komodo Stack**: `reyday` at `/etc/komodo/stacks/reyday/`

## How It Works
- **nginx:alpine** serves a browsable directory listing (autoindex) with HTTP Basic Auth
- Volume mounted **read-write** from `/mnt/pictures/personal/alec/reyday`
- WebDAV `PUT` method enabled for file uploads (DELETE is **not** enabled — users cannot delete files)
- The `mp4` module enables video seeking/scrubbing for .mp4 files without downloading the entire file
- A drag-and-drop upload page at `/upload` uses XMLHttpRequest PUT with progress bars
- nginx workers run as root inside the container (via `sed` on startup) for write access to UID 1000 files
- Based on the same pattern as the `portrait` stack (port 8100, serves hometheater media)

## Proxy Chain
```
Internet → DNS (reyday.1701.me) → 76.159.199.214 (Comcast WAN)
  → port forward → NPM (CT 112, 192.168.0.30) → 192.168.0.179:8105
  → reyday container (nginx:alpine)
```
- NPM proxy host #58 handles SSL termination (Let's Encrypt)
- NPM `client_max_body_size` must be set to `0` for large uploads

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
| `client_max_body_size 0` | Unlimited upload size |
| `dav_methods PUT MKCOL` | Enables file upload and directory creation via WebDAV |
| `create_full_put_path on` | Auto-creates subdirectories on upload |

## Upload Feature
- **URL**: `/upload` — drag-and-drop page with progress bars
- **Method**: HTTP PUT to `/{filename}` (WebDAV)
- **Auth**: Same Basic Auth as browsing (browser sends credentials automatically)
- **Allowed**: Upload (PUT), create directories (MKCOL)
- **Blocked**: Delete (405 Method Not Allowed)
- **File ownership**: Uploaded files owned by `root:root` (UID 0) since nginx workers run as root

## Resource Limits
- CPU: 1.0 (higher than portrait's 0.5 for video streaming)
- Memory: 1024M (higher than portrait's 512M for MP4 buffer overhead)
- PIDs: 50

**Note**: Do NOT enable `aio threads` with a PID limit of 50 — nginx spawns 32 threads per worker, exceeding the limit and crashing all workers.

## Compose File
Location: `/etc/komodo/stacks/reyday/compose.yaml`

```yaml
name: reyday

services:
  reyday:
    image: nginx:alpine
    container_name: reyday
    ports:
      - 8105:80
    volumes:
      - /mnt/pictures/personal/alec/reyday:/usr/share/nginx/html
    command:
      - sh
      - -c
      - |
        rm -f /usr/share/nginx/html/index.html /usr/share/nginx/html/50x.html 2>/dev/null
        sed -i 's/user  nginx;/user  root;/' /etc/nginx/nginx.conf
        echo 'settling:$$apr1$$3vnEJlNW$$2Ts1DGqhURJeGUjpRWP/4/' > /etc/nginx/.htpasswd

        cat > /tmp/upload.html << 'UPLOADHTML'
        <!DOCTYPE html>
        <html><head><title>Upload - Rey Day</title>
        <style>
        body{font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px;background:#fafafa}
        h2{color:#333}
        #drop{border:3px dashed #ccc;padding:60px 20px;text-align:center;border-radius:8px;cursor:pointer;transition:all .2s;background:#fff}
        #drop:hover,#drop.over{border-color:#4a90d9;background:#f0f6ff}
        .file{margin:8px 0;padding:10px;background:#fff;border-radius:4px;border:1px solid #eee}
        .bar-wrap{height:6px;background:#eee;border-radius:3px;margin-top:6px}
        .bar{height:6px;background:#4a90d9;border-radius:3px;width:0%;transition:width .1s}
        .done{color:#2a7;font-weight:bold}
        .err{color:#d33;font-weight:bold}
        a{color:#4a90d9}
        </style></head><body>
        <h2>Upload Files</h2>
        <p><a href="/">Back to files</a></p>
        <div id="drop" onclick="document.getElementById('f').click()">
        Drag and drop files here<br>or click to browse
        <input type="file" id="f" multiple style="display:none">
        </div>
        <div id="list"></div>
        <script>
        var d=document.getElementById('drop');
        d.ondragover=function(e){e.preventDefault();d.classList.add('over')};
        d.ondragleave=function(){d.classList.remove('over')};
        d.ondrop=function(e){e.preventDefault();d.classList.remove('over');go(e.dataTransfer.files)};
        document.getElementById('f').onchange=function(e){go(e.target.files)};
        function go(files){for(var i=0;i<files.length;i++)up(files[i])}
        function up(f){
          var el=document.createElement('div');el.className='file';
          el.innerHTML=f.name+' ('+sz(f.size)+')<div class="bar-wrap"><div class="bar"></div></div>';
          document.getElementById('list').appendChild(el);
          var bar=el.querySelector('.bar'),x=new XMLHttpRequest();
          x.upload.onprogress=function(e){if(e.lengthComputable)bar.style.width=Math.round(e.loaded/e.total*100)+'%'};
          x.onload=function(){if(x.status>=200&&x.status<300){el.innerHTML='<span class="done">'+f.name+' ('+sz(f.size)+') done</span>';}else{el.innerHTML='<span class="err">'+f.name+' failed: '+x.status+'</span>';}};
          x.onerror=function(){el.innerHTML='<span class="err">'+f.name+' upload failed</span>'};
          x.open('PUT','/'+encodeURIComponent(f.name));x.send(f);
        }
        function sz(b){if(b<1024)return b+'B';if(b<1048576)return(b/1024).toFixed(1)+'KB';if(b<1073741824)return(b/1048576).toFixed(1)+'MB';return(b/1073741824).toFixed(1)+'GB'}
        </script></body></html>
        UPLOADHTML

        cat > /etc/nginx/conf.d/default.conf << 'NGINXCONF'
        server {
          listen 80;
          sendfile on;
          tcp_nopush on;
          tcp_nodelay on;
          output_buffers 2 1m;
          keepalive_timeout 300s;
          send_timeout 300s;
          client_max_body_size 0;
          location / {
            auth_basic "Restricted";
            auth_basic_user_file /etc/nginx/.htpasswd;
            root /usr/share/nginx/html;
            autoindex on;
            autoindex_exact_size off;
            autoindex_localtime on;
            dav_methods PUT MKCOL;
            create_full_put_path on;
          }
          location ~* \.mp4$ {
            auth_basic "Restricted";
            auth_basic_user_file /etc/nginx/.htpasswd;
            root /usr/share/nginx/html;
            mp4;
            mp4_buffer_size 4m;
            mp4_max_buffer_size 16m;
            dav_methods PUT;
          }
          location = /upload {
            auth_basic "Restricted";
            auth_basic_user_file /etc/nginx/.htpasswd;
            alias /tmp/upload.html;
          }
        }
        NGINXCONF

        nginx -g 'daemon off;'
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
1. Copy `/etc/komodo/stacks/reyday/` to a new stack name
2. Change the volume mount path, container name, port, and stack name
3. Generate a new htpasswd hash: `docker run --rm httpd:alpine htpasswd -nb username password`
4. Escape `$` as `$$` in the compose file (Docker Compose requirement)
5. Deploy via Komodo UI

## Verification
```bash
# Container running
docker ps --filter name=reyday

# Auth works
curl -u settling:friends http://192.168.0.179:8105/

# No-auth rejected (expect 401)
curl -o /dev/null -w '%{http_code}' http://192.168.0.179:8105/

# Upload page loads
curl -u settling:friends http://192.168.0.179:8105/upload

# Upload a test file (expect 201)
echo 'test' | curl -u settling:friends -T - http://192.168.0.179:8105/test.txt -w '%{http_code}'

# DELETE is blocked (expect 405)
curl -u settling:friends -X DELETE http://192.168.0.179:8105/test.txt -w '%{http_code}'

# Range requests work (video seeking)
curl -u settling:friends -H "Range: bytes=0-1023" -I http://192.168.0.179:8105/GOPR9986.MP4
# Should return 206 Partial Content
```

## Troubleshooting
- **Workers crashing with `pthread_create() failed`**: PID limit too low for `aio threads`. Remove `aio threads` and `directio` directives, or increase PID limit significantly (250+).
- **401 on correct password**: Verify the htpasswd hash — regenerate with `docker run --rm httpd:alpine htpasswd -nb settling friends` and ensure `$` is escaped as `$$` in compose.
- **Can't browse directory**: Check the volume mount path exists on the host and nginx has read access.
- **Upload fails with 403**: nginx workers need write permission. Verify `sed -i 's/user nginx;/user root;/'` ran successfully — check `docker logs reyday`.
- **Upload fails with 413 (Request Entity Too Large)**: Check NPM proxy host config — set `client_max_body_size 0;` in the Advanced tab.
- **Uploaded files not visible via Samba**: Files are owned by root:root. Samba should still serve them if the share config allows. If not, add a cron job to `chown 1000:1000` new files.
