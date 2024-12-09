from flask import Flask
from flask import Flask, request, url_for, session, redirect, render_template, jsonify
import re
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Define constants
CLIENT_ID = "06512c82e38d4bce9e275f251f0c764f"
CLIENT_SECRET = "964777701e984cb5a113bc7819984479"

# Flask app initialization
app = Flask(__name__)
app.secret_key = "replace_with_a_secure_secret_key"

# Spotify OAuth helper
def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=url_for(
            "redirectPage", _external=True),
        scope="user-top-read user-library-read"
    )

@app.route('/')
def index():
    return render_template('snswrapped.html')

@app.route('/login')
def login():
    # This constructs the full external URL for the redirectPage route
    redirect_uri = url_for("redirectPage", _external=True)
    print("Redirect URI:", redirect_uri)  # Debug print to confirm the full URL

    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=redirect_uri,
        scope="user-top-read user-library-read"
    )
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/redirectPage')
def redirectPage():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    if code:
        token_info = sp_oauth.get_access_token(code)
        session['TOKEN_INFO'] = token_info
        print("Redirect URI:", url_for("redirectPage", _external=True))
        return redirect(url_for("snsWrapped"))
    else:
        return "Authorization failed. Please try again.", 400

def get_token():
    token_info = session.get('TOKEN_INFO', None)
    if not token_info:
        return None
    sp_oauth = create_spotify_oauth()
    # Refresh token if expired
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['TOKEN_INFO'] = token_info
    return token_info

@app.route('/snsWrapped')
def snsWrapped():
    token_info = get_token()
    if not token_info:
        return redirect(url_for("login"))
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Helper function to normalize album names
    def normalize_album_name(album_name):
        # Remove text in parentheses, strip whitespace, and convert to lowercase
        album_name = re.sub(r'\s*\[.*?\]\s*', '', album_name)  # Remove text in square brackets
        album_name = re.sub(r'\s*\(.*?\)\s*', '', album_name)  # Remove text in parentheses
        album_name = album_name.strip().lower()
        # Remove common version indicators like "Deluxe" or "Til Dawn Edition"
        album_name = re.sub(r'\s*(deluxe|til dawn edition|special edition|remastered)\s*', '', album_name)
        return album_name
    def normalize_album_name_in_song(album_name):
        # Remove specific terms like "Deluxe", "Deluxe Edition", "Platinum Edition" from album names
        album_name = re.sub(r'\s*(deluxe|deluxe version|deluxe edition|platinum edition)\s*', '', album_name, flags=re.IGNORECASE)

        # Remove text in square brackets, but preserve content in parentheses
        album_name = re.sub(r'\s*\[.*?\]\s*', '', album_name)
        return album_name
    def clean_song_name(song_name):

        # Remove all other parentheses or square brackets
        song_name = re.sub(r'\s*\(.*?\)\s*', '', song_name)  # Remove text in parentheses
        song_name = re.sub(r'\s*\[.*?\]\s*', '', song_name)  # Remove text in square brackets

        return song_name.strip()

    try:
        # Initialize an empty list to hold all top songs
        user_top_songs = []

        # Define the limit per request and total desired tracks
        limit = 50
        total_tracks = 500
        time_range = "long_term"

        # Keywords to look for in album names
        keywords = ["please", "espresso", "short"]

        # Fetch the top songs in batches of 50
        for offset in range(0, total_tracks, limit):
            top_songs_batch = sp.current_user_top_tracks(
                limit=limit,
                offset=offset,
                time_range=time_range
            )
            # Filter items based on album name keywords
            for song in top_songs_batch['items']:
                album_name = song['album']['name'].lower()
                if any(keyword in album_name for keyword in keywords):
                    user_top_songs.append(song)
        # Filter for Sabrina Carpenter songs
        taylor_swift_songs = [
            {
                'song_name': clean_song_name(song['name']),
                'album_name': normalize_album_name_in_song(song['album']['name']),
                'additional_image': f"static/images/{i+1}-.png" if i < 5 else None  # Add additional image for first 5
            }
            for i, song in enumerate(user_top_songs) if any(artist['name'] == 'Sabrina Carpenter' for artist in song['artists'])
        ]

        # Return songs with album name, album image, and sorted albums
        return jsonify({
            "songs": [{"song_name": song['song_name'], "album_name": normalize_album_name_in_song(song['album_name'])} for song in taylor_swift_songs]
        })

    except spotipy.SpotifyException as e:
        return f"Error retrieving data: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)