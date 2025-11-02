# app.py

# Put these two lines FIRST, before any other imports
import eventlet
eventlet.monkey_patch()

import os
import subprocess
import json
import traceback
from urllib.parse import unquote

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key' 
DOWNLOAD_FOLDER = 'downloads'
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
socketio = SocketIO(app)

os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Main route to display the HTML page
@app.route('/')
def index():
    return render_template('index.html')

# NEW: Universal route to fetch metadata before downloading
@app.route('/get-info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required.'}), 400

    if 'spotify.com' in url:
        # For Spotify, we skip fetching metadata to ensure reliability.
        # We just confirm it's a Spotify link and let the user proceed.
        return jsonify({'success': True, 'type': 'spotify'})
    
    elif 'youtube.com' in url or 'youtu.be' in url:
        try:
            # Use yt-dlp to get video metadata as JSON
            command = ["yt-dlp", "--print-json", "--skip-download", url]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            video_info = json.loads(result.stdout)
            
            return jsonify({
                'success': True,
                'type': 'youtube',
                'title': video_info.get('title'),
                'thumbnail': video_info.get('thumbnail')
            })
        except Exception as e:
            traceback.print_exc()
            return jsonify({'error': 'Failed to fetch YouTube video information.'}), 500
    else:
        return jsonify({'error': 'Please provide a valid Spotify or YouTube URL.'}), 400


# NEW: Universal WebSocket handler for all download types
@socketio.on('start_download')
def handle_download(data):
    url = data.get('url')
    # Format will be 'spotify', 'audio', or 'video'
    download_format = data.get('format')

    cleaned_url = url.split('?')[0]
    
    command = []
    
    if download_format == 'spotify':
        command = [
            "spotdl", "download", cleaned_url, 
            "--output", app.config['DOWNLOAD_FOLDER']
        ]
    elif download_format == 'audio':
        command = [
            "yt-dlp", "-x", "--audio-format", "mp3",
            "-o", f"{app.config['DOWNLOAD_FOLDER']}/%(title)s.%(ext)s",
            cleaned_url
        ]
    elif download_format == 'video':
        command = [
            "yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", f"{app.config['DOWNLOAD_FOLDER']}/%(title)s.%(ext)s",
            cleaned_url
        ]
    
    if not command:
        socketio.emit('download_error', {'error': 'Invalid download format specified.'})
        return

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8')
        
        for line in iter(process.stdout.readline, ''):
            print(line.strip()) # For debugging
            socketio.emit('progress_update', {'data': line.strip()})
        
        process.stdout.close()
        process.wait()
        
        if process.returncode != 0:
            socketio.emit('download_error', {'error': 'Download process failed. Check server logs for details.'})
            return

        # Find the most recently created file in the downloads folder
        files = [os.path.join(app.config['DOWNLOAD_FOLDER'], f) for f in os.listdir(app.config['DOWNLOAD_FOLDER'])]
        if not files:
            socketio.emit('download_error', {'error': 'Process finished but no file was found.'})
            return
            
        latest_file = max(files, key=os.path.getctime)
        # We need to unquote the filename in case it has URL-encoded characters
        filename = unquote(os.path.basename(latest_file))

        socketio.emit('download_complete', {'filename': filename})

    except Exception as e:
        traceback.print_exc()
        socketio.emit('download_error', {'error': 'A critical server error occurred during download.'})


# Route to serve the downloaded file
@app.route('/files/<path:filename>')
def get_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    socketio.run(app, debug=True)