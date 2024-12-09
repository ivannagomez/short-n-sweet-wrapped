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
    return render_template('index.html')

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
        return redirect(url_for("swiftieWrapped"))
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

@app.route('/swiftieWrapped')
def swiftieWrapped():
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
        # Check for the "(10 Minute Version)" exception
        if "(10 Minute Version)" in song_name:
            # Temporarily replace it with a unique placeholder
            song_name = song_name.replace("(10 Minute Version)", "-EXCEPTION-")

        # Remove all other parentheses or square brackets
        song_name = re.sub(r'\s*\(.*?\)\s*', '', song_name)  # Remove text in parentheses
        song_name = re.sub(r'\s*\[.*?\]\s*', '', song_name)  # Remove text in square brackets

        # Restore the "(10 Minute Version)" exception
        song_name = song_name.replace("-EXCEPTION-", "(10 Minute Version)")

        return song_name.strip()

    try:
        user_top_songs_1 = sp.current_user_top_tracks(
            limit=50,
            offset=0,
            time_range="long_term"
        )

        user_top_songs_2 = sp.current_user_top_tracks(
            limit=50,
            offset=50,
            time_range="long_term"
        )

        user_top_songs = user_top_songs_1['items'] + user_top_songs_2['items']

        # Filter for Taylor Swift songs
        taylor_swift_songs = [
            {
                'song_name': clean_song_name(song['name']),
                'album_name': normalize_album_name_in_song(song['album']['name']),
                'album_image': song['album']['images'][0]['url'],
                'additional_image': f"static/images/{i+1}.png" if i < 5 else None  # Add additional image for first 5
            }
            for i, song in enumerate(user_top_songs) if any(artist['name'] == 'Taylor Swift' for artist in song['artists'])
        ]

        # Count album occurrences, using normalized album names
        album_counts = {}
        for track in user_top_songs:
            if any(artist['name'] == 'Taylor Swift' for artist in track['artists']):
                album_name = normalize_album_name(track['album']['name'])
                if album_name in album_counts:
                    album_counts[album_name] += 1
                else:
                    album_counts[album_name] = 1

        # Sort albums by play count (most to least)
        sorted_albums = sorted(album_counts.items(), key=lambda x: x[1], reverse=True)

        # Return songs with album name, album image, and sorted albums
        return jsonify({
            "songs": [{"song_name": clean_song_name(song['song_name']), "album_name": normalize_album_name_in_song(song['album_name']), "album_image": song['album_image']} for song in taylor_swift_songs],
            "albums": [album[0] for album in sorted_albums]
        })

    except spotipy.SpotifyException as e:
        return f"Error retrieving data: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)