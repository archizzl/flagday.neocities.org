#!/usr/bin/env bash
# Regenerate the Charts list in music.html from songs/complete_songs/.
# Each direct subfolder of complete_songs/ is treated as an album; each file
# inside becomes a link labelled by its filename (underscores → spaces,
# extension stripped). Run whenever files or folders change.

set -euo pipefail
cd "$(dirname "$0")"

DIR="songs/complete_songs"
FILE="music.html"
START="<!-- CHARTS:START -->"
END="<!-- CHARTS:END -->"

if [ ! -d "$DIR" ]; then
    echo "error: $DIR not found" >&2
    exit 1
fi
if ! grep -q "$START" "$FILE" || ! grep -q "$END" "$FILE"; then
    echo "error: $FILE is missing '$START' / '$END' markers" >&2
    exit 1
fi

block=$(mktemp)
tmp=$(mktemp)
trap 'rm -f "$block" "$tmp"' EXIT

url_encode() {
    # Percent-encode reserved chars so paths with spaces work in href.
    python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$1"
}

album_count=0
song_count=0

# Iterate direct subfolders alphabetically.
while IFS= read -r -d '' album_dir; do
    album=$(basename "$album_dir")
    album_enc=$(url_encode "$album")

    {
        printf '                            <li class="charts-album">\n'
        printf '                                <div class="charts-album-title">%s</div>\n' "$album"
        printf '                                <ul class="charts-album-songs">\n'
    } >> "$block"

    while IFS= read -r -d '' song; do
        fname=$(basename "$song")
        stem="${fname%.*}"
        label="${stem//_/ }"
        fname_enc=$(url_encode "$fname")
        printf '                                    <li><a href="%s/%s/%s" target="_blank" rel="noopener">%s</a></li>\n' \
            "$DIR" "$album_enc" "$fname_enc" "$label" >> "$block"
        song_count=$((song_count + 1))
    done < <(find "$album_dir" -mindepth 1 -maxdepth 1 -type f -print0 | sort -z)

    {
        printf '                                </ul>\n'
        printf '                            </li>\n'
    } >> "$block"

    album_count=$((album_count + 1))
done < <(find "$DIR" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

awk -v startpat="$START" -v endpat="$END" -v newfile="$block" '
    index($0, startpat) {
        print
        while ((getline line < newfile) > 0) print line
        close(newfile)
        inblock = 1
        next
    }
    index($0, endpat) { inblock = 0 }
    !inblock { print }
' "$FILE" > "$tmp"

mv "$tmp" "$FILE"
echo "Wrote $song_count song(s) across $album_count album(s) to $FILE."
