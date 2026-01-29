# Unmanic Configuration

## Container Info
- **Container**: LXC 105 (unmanic)
- **IP**: 192.168.0.207
- **Web UI**: http://192.168.0.207:8888
- **Library Path**: /library (mounted from /mnt/hometheater on host)

## Goal
Process media files for audio/subtitle standardization:
- Keep English audio tracks only
- Add AAC stereo track for compatibility/mobile
- Extract English subtitles to external .srt files
- Remove all embedded subtitles

**Note**: Video codec is NOT changed (no HEVC transcoding)

## Installed Plugins
1. **extract_srt_subtitles_to_files** - Extract English subs to .srt
2. **convert_subtitle_streams_ass_to_srt** - Convert ASS subtitles to SRT format
3. **remove_stream_by_language** - Remove non-English audio
4. **add_extra_stereo_audio** - Create AAC stereo from best audio
5. **remove_all_subtitles** - Remove embedded subtitles

## Worker - Processing File Flow (in order)
1. extract_srt_subtitles_to_files
2. convert_subtitle_streams_ass_to_srt
3. remove_stream_by_language
4. add_extra_stereo_audio
5. remove_all_subtitles

## Plugin Configuration

### remove_stream_by_language
- Remove audio languages: spa,fra,deu,ita,por,jpn,kor,zho,chi,rus,ara,hin,tha,vie,pol,nld,swe,nor,dan,fin,tur,ces,hun,ron,ukr,heb,ind,msa,fil,ben,tam,tel,mar,guj,kan,mal,pan,per,urd,fas
- Keep: English (eng, en)

### add_extra_stereo_audio
- Source language: eng
- Use libfdk_aac: false (uses native aac)
- Keep original audio: yes
- Make stereo default: no

### extract_srt_subtitles_to_files
- Languages: eng,en
- Include title in filename: no

## Hardware
- Intel Iris Xe GPU passed through (available for future use)
- Devices: /dev/dri/card0, /dev/dri/renderD128

## Storage
- Library: 29TB total (15TB used, 14TB free)
- Contains: Movies, TV Shows

## To Enable
1. Go to http://192.168.0.207:8888
2. Settings > Libraries > Edit Home Theater
3. Enable Library Scanner and/or File Monitor
4. Save and processing will begin

Updated: 2026-01-11
