"""Curated catalogue shown in the UI. Any site yt-dlp or gallery-dl supports still works."""
SITES = [
    ('YouTube', 'youtube.com', 'video'), ('Vimeo', 'vimeo.com', 'video'), ('Dailymotion', 'dailymotion.com', 'video'),
    ('Twitch clips', 'twitch.tv', 'video'), ('TikTok', 'tiktok.com', 'video'), ('Reddit', 'reddit.com', 'video'),
    ('Bilibili', 'bilibili.com', 'video'), ('Rumble', 'rumble.com', 'video'), ('Streamable', 'streamable.com', 'video'),
    ('SoundCloud', 'soundcloud.com', 'video'),
    ('X / Twitter', 'x.com', 'social'), ('Instagram', 'instagram.com', 'social'), ('Facebook', 'facebook.com', 'social'),
    ('Bluesky', 'bsky.app', 'social'), ('Tumblr', 'tumblr.com', 'social'), ('Pinterest', 'pinterest.com', 'social'),
    ('Imgur', 'imgur.com', 'image'), ('DeviantArt', 'deviantart.com', 'image'), ('Flickr', 'flickr.com', 'image'),
    ('ArtStation', 'artstation.com', 'image'),
]


def catalogue():
    return [{'name': name, 'domain': domain, 'category': category} for name, domain, category in SITES]
