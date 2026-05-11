# Authors:
##### Ivan-Serralta
##### HTML-Loaded (Leo Scheiber)

Song Of The Day (SOTD) — Code Documentation & User Manual
Last updated: 2026-05-11

1) Overview
Song Of The Day is a Django web app where users connect Spotify, post one song per day with a caption, view a friends feed, react with emojis, and reply to captions.

Key features
- Authentication (login/signup)
- Spotify OAuth connect (connects your Spotify account)
- Feed of recent SongShares (rolling history window)
- One-share-per-day limit (with cooldown timer)
- Emoji reactions (preset + optional support for arbitrary emoji values)
- Replies on captions (shows username + relative time)
- Infinite scrolling feed pagination for performance

2) Quick Start (Developer)
Prerequisites
- Python (project includes a venv folder; you can also use your own)
- Django and dependencies installed (see the project environment)

Run locally
1. Open a terminal in the project folder:
   C:\Users\IvanS\OneDrive\Documents\SongOfTheDay

2. Run migrations:
   python manage.py migrate

3. Start the dev server:
   python manage.py runserver

4. Open:
   http://127.0.0.1:8000/

Spotify configuration
- Spotify OAuth requires values in environment / settings:
  - SPOTIFY_CLIENT_ID
  - SPOTIFY_CLIENT_SECRET
  - SPOTIFY_REDIRECT_URI

3) User Manual
3.1 Sign up / Log in
- Use the Signup page to create an account.
- Username uniqueness is enforced case-insensitively.
  Example: "Ivan" and "ivan" cannot both exist.

3.2 Connect Spotify
- On Home and Feed, if you are logged in but not connected to Spotify,
  a popup prompts you to connect.
- Click “Connect” to start Spotify OAuth.

3.3 Share a song (once per day)
- Go to Feed.
- Search Spotify or paste a Spotify track URL / URI.
- Add a caption.
- Click Share.

Limit behavior
- You can share one song per day.
- If you already posted today, the app shows a cooldown timer until your next allowed post (local midnight).

3.4 View feed and history
- The feed shows up to 3 days of history.
- Older items are automatically removed.
- Infinite scrolling loads more items as you scroll down.

3.5 React to a song
- Tap/click the “React” pill (or existing reaction chips).
- A Reactions modal appears.
- Tap one of the preset emojis to toggle your reaction.

Custom emoji
- The backend supports receiving arbitrary emoji values (non-ASCII) up to 20 characters.
- The UI entry point for custom emoji input is currently disabled.

3.6 Reply to a caption
- Expand the caption by tapping/clicking it.
- A Reply button appears.
- Replies must be up to 4 sentences (1–4).
- Replies show the author’s username and a relative timestamp (e.g., “2 min ago”, “1 hour ago”, “2 days ago”).

4) Codebase Guide (Developer)
Project layout (high level)
- manage.py: Django entry point
- mysite/: project settings/urls/views
- accounts/: profile + Spotify integration
- feed/: SongShare, reactions, replies, feed logic
- social/: friendships
- templates/: HTML templates (base + feature pages)

Core models
- feed.models.SongShare
  - user: OneToOne (current design enforces one share record per user, updated daily)
  - track_input: Spotify URL/URI
  - caption: optional text
  - created_at

- feed.models.SongReaction
  - share: FK -> SongShare
  - user: FK -> auth user
  - emoji: up to 20 chars
  - created_at
  - unique constraint: (share, user, emoji)

- feed.models.SongReply
  - share: FK -> SongShare
  - user: FK -> auth user
  - body: text
  - created_at

Key endpoints (feed app)
- GET  /feed/                       feed page
- GET  /feed/page/                  paged feed loading (returns HTML + cursor)
- GET  /feed/reactions/<share_id>/  returns reaction counts + mine
- POST /feed/react/<share_id>/      toggle reaction
- GET  /feed/replies/<share_id>/    list replies
- POST /feed/reply/<share_id>/      create reply

Templates
- templates/base.html
  - Global styling
  - Modal overlay component
  - Spotify connect prompt modal (conditionally shown)

- templates/feed/feed.html
  - Feed page
  - Reactions modal JS
  - Reply UI JS
  - Infinite scroll JS

- templates/feed/_share_card.html
  - Partial template used for initial feed render and for infinite-scroll appended HTML

Notes on feed pagination
- Server uses a cursor based on (created_at, id)
- Client requests /feed/page/?cursor=<iso>&cursor_id=<id>
- Response returns HTML snippets plus next cursor.

3-day history cleanup
- Each request that builds the feed queryset deletes SongShare items older than 3 days.

5) Troubleshooting
Spotify popup keeps appearing
- The popup appears when you are logged in but not connected.
- If you dismiss it, the dismiss is remembered for the current browser session.

No Spotify search results
- Make sure Spotify is connected.
- Ensure SPOTIFY_CLIENT_ID / SECRET / REDIRECT_URI are configured.

Replies fail to send
- Reply body must be 1–4 sentences.

Feed stops loading older posts
- After 3 days, older shares are removed.
- Infinite scroll only loads available shares in that time window.
